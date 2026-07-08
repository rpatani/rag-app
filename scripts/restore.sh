#!/usr/bin/env bash
# Restore the RAG app from a backup produced by backup.sh.
#
# Usage: ./scripts/restore.sh backups/ragdb_YYYYmmdd_HHMMSS.sql.gz [backups/documents_YYYYmmdd_HHMMSS.tar.gz]
#
# The Postgres container must be running (docker compose up -d postgres).
# Restoring REPLACES current database contents — you will be asked to confirm.
set -euo pipefail

cd "$(dirname "$0")/.."

DB_DUMP="${1:?Usage: restore.sh <ragdb_*.sql.gz> [documents_*.tar.gz]}"
DOCS_ARCHIVE="${2:-}"

POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2- || true)"
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- || true)"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"

if [ -z "${POSTGRES_USER}" ]; then
  echo "ERROR: POSTGRES_USER not found in .env" >&2
  exit 1
fi

[ -f "${DB_DUMP}" ] || { echo "ERROR: ${DB_DUMP} not found" >&2; exit 1; }

echo "This will REPLACE the contents of database '${POSTGRES_DB}'."
read -r -p "Type 'restore' to continue: " CONFIRM
[ "${CONFIRM}" = "restore" ] || { echo "Aborted."; exit 1; }

echo "[$(date -Iseconds)] Restoring database from ${DB_DUMP}..."
gunzip -c "${DB_DUMP}" | docker compose exec -T postgres psql \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --quiet

if [ -n "${DOCS_ARCHIVE}" ]; then
  [ -f "${DOCS_ARCHIVE}" ] || { echo "ERROR: ${DOCS_ARCHIVE} not found" >&2; exit 1; }
  echo "[$(date -Iseconds)] Restoring documents directory from ${DOCS_ARCHIVE}..."
  tar -xzf "${DOCS_ARCHIVE}"
fi

echo "[$(date -Iseconds)] Restore complete. Restart the backend: docker compose restart backend"
