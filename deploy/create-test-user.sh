#!/bin/sh
set -eu

project_dir="${RYTHM_MUSIC_PROJECT_DIR:-/opt/rythm-music}"
shared_env="${RYTHM_SHARED_DB_ENV:-${project_dir}/deploy/shared-postgres.env}"
music_env="${RYTHM_MUSIC_ENV:-${project_dir}/.env.production}"
test_email="music-test@rythmmusic.site"
test_username="Music Acceptance Tester"

test -f "$shared_env"
test -f "$music_env"

if [ ! -t 0 ]; then
  printf '%s\n' "Run this command from an interactive terminal." >&2
  exit 1
fi

compose() {
  docker compose \
    --env-file "$shared_env" \
    --env-file "$music_env" \
    -f "${project_dir}/docker-compose.prod.yml" \
    "$@"
}

restore_terminal() {
  stty echo 2>/dev/null || true
}
trap restore_terminal EXIT HUP INT TERM

printf 'Password for %s (at least 12 characters): ' "$test_email" >&2
stty -echo
IFS= read -r password
stty echo
printf '\n' >&2

if [ "${#password}" -lt 12 ]; then
  printf '%s\n' "Password must contain at least 12 characters." >&2
  exit 1
fi

password_hash="$(
  printf '%s' "$password" |
    compose exec -T backend python -c \
      'import sys; from app.core.security import hash_password, validate_password_strength; password = sys.stdin.read(); validate_password_strength(password); print(hash_password(password))'
)"
unset password

terms_version="$(
  compose exec -T backend python -c \
    'from app.core.config import get_settings; print(get_settings().terms_version)'
)"

compose exec -T \
  -e "RYTHM_TEST_EMAIL=$test_email" \
  -e "RYTHM_TEST_USERNAME=$test_username" \
  -e "RYTHM_TEST_PASSWORD_HASH=$password_hash" \
  -e "RYTHM_TEST_TERMS_VERSION=$terms_version" \
  postgres sh -c \
    'PGPASSWORD="$MUSIC_POSTGRES_PASSWORD" psql \
      -h 127.0.0.1 \
      -v ON_ERROR_STOP=1 \
      -v test_email="$RYTHM_TEST_EMAIL" \
      -v test_username="$RYTHM_TEST_USERNAME" \
      -v test_password_hash="$RYTHM_TEST_PASSWORD_HASH" \
      -v test_terms_version="$RYTHM_TEST_TERMS_VERSION" \
      -U "$MUSIC_POSTGRES_USER" \
      -d "$MUSIC_POSTGRES_DB"' <<'SQL'
INSERT INTO users (
    email,
    username,
    hashed_password,
    locale,
    role,
    status,
    points_balance,
    is_email_verified,
    email_verified_at,
    created_at,
    updated_at
)
VALUES (
    :'test_email',
    :'test_username',
    :'test_password_hash',
    'zh-CN',
    'USER',
    'ACTIVE',
    0,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (email) DO UPDATE
SET username = EXCLUDED.username,
    hashed_password = EXCLUDED.hashed_password,
    locale = EXCLUDED.locale,
    role = 'USER',
    status = 'ACTIVE',
    is_email_verified = TRUE,
    email_verified_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
RETURNING id AS test_user_id
\gset

DELETE FROM auth_sessions WHERE user_id = :test_user_id;
DELETE FROM email_verification_tokens WHERE user_id = :test_user_id;
DELETE FROM password_reset_tokens WHERE user_id = :test_user_id;

INSERT INTO user_consents (
    user_id,
    document_type,
    document_version,
    ip_address,
    consented_at
)
VALUES (
    :test_user_id,
    'terms',
    :'test_terms_version',
    NULL,
    CURRENT_TIMESTAMP
)
ON CONFLICT (user_id, document_type, document_version) DO NOTHING;

INSERT INTO audit_logs (
    user_id,
    event_type,
    result,
    metadata_redacted,
    created_at
)
VALUES (
    :test_user_id,
    'test_user_provisioned',
    'success',
    '{"source":"deploy/create-test-user.sh"}',
    CURRENT_TIMESTAMP
);

SELECT
    id,
    email,
    username,
    status,
    is_email_verified,
    points_balance
FROM users
WHERE id = :test_user_id;
SQL

printf '\nTest user is ready: %s\n' "$test_email"
