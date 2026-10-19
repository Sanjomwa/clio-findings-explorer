#!/usr/bin/env bash
# Fire the finding-page alert on purpose (product spec 7.3, docs/alerting.md).
# Stops only the db service, then requests finding pages through the frontend for about two
# minutes. It does NOT restart the db: that is the on-call agent's job (issue #7).
# Restore by hand with: docker compose start db
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1

BASE=${BASE_URL:-http://127.0.0.1:8080}
REQUESTS=${REQUESTS:-24}   # spec 7.3 needs at least 10 in the window
PAUSE=${PAUSE:-5}          # 24 requests x 5 s is about two minutes

date -u +"%H:%M:%SZ stopping db"
docker compose stop db

for i in $(seq 1 "$REQUESTS"); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$BASE/api/findings")
  printf '%s request %s/%s GET /api/findings -> %s\n' "$(date -u +%H:%M:%SZ)" "$i" "$REQUESTS" "$code"
  sleep "$PAUSE"
done

echo
echo "The db is still stopped. The alert should be Pending or Firing at http://127.0.0.1:3000/alerting/list"
echo "Restore it by hand with: docker compose start db"
