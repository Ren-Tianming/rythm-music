#!/bin/sh
set -eu

project_dir="${RYTHM_MUSIC_PROJECT_DIR:-/opt/rythm-music}"
shared_env="${RYTHM_SHARED_DB_ENV:-${project_dir}/deploy/shared-postgres.env}"
music_env="${RYTHM_MUSIC_ENV:-${project_dir}/.env.production}"
backup_dir="${RYTHM_BACKUP_DIR:-/var/backups/rythm-postgres}"
retention_days="${RYTHM_BACKUP_RETENTION_DAYS:-7}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

test -f "$shared_env"
test -f "$music_env"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

compose() {
  docker compose \
    --env-file "$shared_env" \
    --env-file "$music_env" \
    -f "${project_dir}/docker-compose.prod.yml" \
    "$@"
}

for database in music chatbot; do
  target="${backup_dir}/${database}-${timestamp}.dump"
  temporary="${target}.partial"
  if [ "$database" = "music" ]; then
    database_variable=MUSIC_POSTGRES_DB
  else
    database_variable=CHATBOT_POSTGRES_DB
  fi
  compose exec -T postgres sh -c \
    "pg_dump --format=custom --compress=9 --no-owner --no-privileges --username \"\$POSTGRES_USER\" --dbname \"\$${database_variable}\"" \
    > "$temporary"
  test -s "$temporary"
  chmod 600 "$temporary"
  mv "$temporary" "$target"
done

globals_target="${backup_dir}/globals-${timestamp}.sql"
globals_temporary="${globals_target}.partial"
compose exec -T postgres sh -c \
  'pg_dumpall --globals-only --no-role-passwords --username "$POSTGRES_USER"' \
  > "$globals_temporary"
test -s "$globals_temporary"
chmod 600 "$globals_temporary"
mv "$globals_temporary" "$globals_target"

find "$backup_dir" -type f \( -name 'music-*.dump' -o -name 'chatbot-*.dump' -o -name 'globals-*.sql' \) -mtime "+$retention_days" -delete
printf '%s\n' "$backup_dir"
