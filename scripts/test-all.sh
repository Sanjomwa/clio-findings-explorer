#!/usr/bin/env bash
# Run every test suite in order and stop on the first failure.
# Needs the compose db running and seeded:
#   docker compose up -d db && docker compose run --rm seed
set -uo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found. Run: cp .env.example .env" >&2
  exit 1
fi
set -a; . ./.env; set +a

DB_HOST=localhost
DB_PORT=${DB_PORT:-55432}
export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@$DB_HOST:$DB_PORT/$POSTGRES_DB"

if ! (exec 3<>"/dev/tcp/$DB_HOST/$DB_PORT") 2>/dev/null; then
  echo "The database is not reachable on $DB_HOST:$DB_PORT." >&2
  echo "Start and seed it first: docker compose up -d db && docker compose run --rm seed" >&2
  exit 1
fi

summary=()
run() {
  local name=$1; shift
  echo
  echo "=== $name"
  if "$@"; then
    summary+=("PASS  $name")
  else
    summary+=("FAIL  $name")
    echo
    printf '%s\n' "${summary[@]}"
    exit 1
  fi
}

run "hook tests" uv run --no-project --with pyyaml python -m unittest discover -s agent-hooks/tests -v
run "snapshot export tests" uv run --no-project --with pyyaml python -m unittest discover -s ops/tests -v
run "backend unit" uv run --directory backend pytest tests/unit -v
run "backend integration" uv run --directory backend pytest tests/integration -v
run "MCP server" uv run --directory mcp-server pytest -v
run "frontend" bash -c 'cd frontend && npm ci --silent && npm test'

echo
printf '%s\n' "${summary[@]}"
