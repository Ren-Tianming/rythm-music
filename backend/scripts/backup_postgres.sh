#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=rythm_music}"
: "${PGUSER:=rythm_user}"
: "${BACKUP_DIR:=./backups}"
: "${PGPASSWORD:?PGPASSWORD is required}"

mkdir -p "${BACKUP_DIR}"
timestamp="$(date +%Y%m%d_%H%M%S)"
output="${BACKUP_DIR}/${PGDATABASE}_${timestamp}.dump"

pg_dump --format=custom --file="${output}"
echo "Backup written to ${output}"
