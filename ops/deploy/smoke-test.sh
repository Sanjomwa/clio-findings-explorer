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

python3 - "$health" <<'PY'
import json
import sys

manifest = json.load(open("data/snapshot/MANIFEST.json"))
health = json.load(open(sys.argv[1]))
assert health["snapshot_version"] == manifest["version"], (health["snapshot_version"], manifest["version"])
assert health["row_counts"]["findings"] == 5, health["row_counts"]
print("ok:", health["snapshot_version"], health["row_counts"]["findings"], "findings")
PY
