#!/usr/bin/env bash
# End-to-end simulation: throwaway Postgres+pgvector container, Alembic
# baseline, then the full upload → ingest → retrieve → delete cycle through
# the real API. Cleans up the container on exit.
#
# Usage: PYTHON=/path/to/venv/bin/python ./scripts/run_e2e.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
CONTAINER=rag_e2e_pg
PORT="${E2E_PG_PORT:-55432}"
URL="postgresql+psycopg://e2euser:e2epass@localhost:${PORT}/e2edb"

cleanup() { docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

echo "── Starting throwaway Postgres (pgvector) on port ${PORT}..."
docker run -d --name "${CONTAINER}" \
  -e POSTGRES_USER=e2euser -e POSTGRES_PASSWORD=e2epass -e POSTGRES_DB=e2edb \
  -p "${PORT}:5432" pgvector/pgvector:pg16 >/dev/null

for i in $(seq 1 30); do
  if docker exec "${CONTAINER}" pg_isready -U e2euser -d e2edb >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "${CONTAINER}" pg_isready -U e2euser -d e2edb >/dev/null

echo "── Applying Alembic baseline..."
(cd backend && DATABASE_URL="${URL}" "${PYTHON}" -m alembic upgrade head)

echo "── Running end-to-end simulation..."
(cd backend && E2E_DATABASE_URL="${URL}" DATABASE_URL="${URL}" \
  "${PYTHON}" -m pytest tests/test_e2e_simulation.py -v)

echo "── E2E simulation passed."
