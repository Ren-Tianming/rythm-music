#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=rythm_music}"
: "${PGUSER:=rythm_user}"
: "${PGPASSWORD:?PGPASSWORD is required}"

backup_file="${1:?Usage: restore_postgres.sh <backup.dump>}"
test -f "${backup_file}"

pg_restore --clean --if-exists --no-owner --dbname="${PGDATABASE}" "${backup_file}"
echo "Restore completed from ${backup_file}"
