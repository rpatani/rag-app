#!/usr/bin/env bash
# Backup the RAG app: Postgres dump + documents directory.
#
# Usage:  ./scripts/backup.sh [backup_dir]
# Cron:   0 2 * * *  cd /path/to/rag-app && ./scripts/backup.sh /mnt/backup/rag >> /var/log/rag-backup.log 2>&1
#
# Keeps the most recent $RETAIN backups (default 14). Restore with restore.sh.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${1:-./backups}"
RETAIN="${RETAIN:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"

# Read DB name/user from .env (never echoed).
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2- || true)"
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- || true)"
POSTGRES_DB="${POSTGRES_DB:-ragdb}"

if [ -z "${POSTGRES_USER}" ]; then
  echo "ERROR: POSTGRES_USER not found in .env" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Dumping database ${POSTGRES_DB}..."
# --clean --if-exists makes the dump directly restorable with plain psql.
docker compose exec -T postgres pg_dump \
  -U "${POSTGRES_USER}" --clean --if-exists "${POSTGRES_DB}" \
  | gzip > "${BACKUP_DIR}/ragdb_${STAMP}.sql.gz"

echo "[$(date -Iseconds)] Archiving documents directory..."
tar -czf "${BACKUP_DIR}/documents_${STAMP}.tar.gz" documents/

# Retention: keep the newest $RETAIN of each artifact type.
for prefix in ragdb documents; do
  ls -1t "${BACKUP_DIR}/${prefix}_"*.gz 2>/dev/null | tail -n "+$((RETAIN + 1))" | xargs -r rm --
done

echo "[$(date -Iseconds)] Backup complete:"
ls -lh "${BACKUP_DIR}/ragdb_${STAMP}.sql.gz" "${BACKUP_DIR}/documents_${STAMP}.tar.gz"
