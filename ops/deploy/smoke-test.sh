#!/usr/bin/env bash
# Smoke test for a deployed environment: /api/health through the frontend URL must report the
# snapshot version in data/snapshot/MANIFEST.json and 5 findings. Run from the repository root.
set -euo pipefail

url="${1:?usage: smoke-test.sh <frontend URL>}"
health="$(mktemp)"
trap 'rm -f "$health"' EXIT

# A scaled-to-zero service needs a moment to start both containers; retry for about 2 minutes.
for attempt in $(seq 1 12); do
  if curl -fsS --max-time 30 "${url%/}/api/health" -o "$health"; then
    break
  fi
  echo "health not ready (attempt ${attempt})"
  [ "$attempt" = 12 ] && { echo "::error::${url}/api/health never answered"; exit 1; }
  sleep 10
done

# Browser security headers on the frontend's own page.
headers="$(curl -fsS --max-time 30 -D - -o /dev/null "${url%/}/")"
for h in content-security-policy x-frame-options x-content-type-options; do
  echo "$headers" | grep -qi "^${h}:" || { echo "::error::${url}/ has no ${h} header"; exit 1; }
done
echo "ok: security headers present"

# A 422 body must not echo the rejected input.
invalid="$(mktemp)"
trap 'rm -f "$health" "$invalid"' EXIT
code="$(curl -sS --max-time 30 -o "$invalid" -w '%{http_code}' "${url%/}/api/findings/%27")"
[ "$code" = 422 ] || { echo "::error::/api/findings/%27 returned ${code}, expected 422"; exit 1; }
python3 - "$invalid" <<'PY'
import json
import sys

for err in json.load(open(sys.argv[1]))["detail"]:
    assert "input" not in err and "ctx" not in err, err
print("ok: 422 body has no input or ctx")
PY

python3 - "$health" <<'PY'
import json
import sys

manifest = json.load(open("data/snapshot/MANIFEST.json"))
health = json.load(open(sys.argv[1]))
assert health["snapshot_version"] == manifest["version"], (health["snapshot_version"], manifest["version"])
assert health["row_counts"]["findings"] == 5, health["row_counts"]
print("ok:", health["snapshot_version"], health["row_counts"]["findings"], "findings")
PY
