#!/bin/sh
set -eu

reject_placeholder() {
  name="$1"
  value="$2"
  normalized="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$normalized" in
    ""|*replace-with*|*replace_with*|*change-me*|*changeme*|*placeholder*|*example.com*|*your-*|*your_*)
      printf '%s\n' "$name contains an empty or placeholder value" >&2
      exit 1
      ;;
  esac
}

require_length() {
  name="$1"
  value="$2"
  minimum="$3"
  if [ "${#value}" -lt "$minimum" ]; then
    printf '%s\n' "$name must contain at least $minimum characters" >&2
    exit 1
  fi
}

require_identifier() {
  name="$1"
  value="$2"
  case "$value" in
    ""|*[!A-Za-z0-9_]*)
      printf '%s\n' "$name must contain only letters, digits, and underscores" >&2
      exit 1
      ;;
  esac
}

require_hex_secret() {
  name="$1"
  value="$2"
  case "$value" in
    *[!A-Fa-f0-9]*)
      printf '%s\n' "$name must be hexadecimal so the database URL remains valid" >&2
      exit 1
      ;;
  esac
}

for name in \
  APP_SECRET \
  POSTGRES_ADMIN_PASSWORD \
  MUSIC_POSTGRES_PASSWORD \
  CHATBOT_POSTGRES_PASSWORD \
  VITE_TURNSTILE_SITE_KEY \
  AUDIO_TURNSTILE_SECRET_KEY \
  AUDIO_SMTP_HOST \
  AUDIO_SMTP_USERNAME \
  AUDIO_SMTP_PASSWORD \
  AUDIO_SMTP_FROM_EMAIL \
  AUDIO_TERMS_VERSION
do
  value="$(printenv "$name")"
  reject_placeholder "$name" "$value"
done

require_length APP_SECRET "$APP_SECRET" 32
require_length POSTGRES_ADMIN_PASSWORD "$POSTGRES_ADMIN_PASSWORD" 32
require_length MUSIC_POSTGRES_PASSWORD "$MUSIC_POSTGRES_PASSWORD" 32
require_length CHATBOT_POSTGRES_PASSWORD "$CHATBOT_POSTGRES_PASSWORD" 32
require_hex_secret POSTGRES_ADMIN_PASSWORD "$POSTGRES_ADMIN_PASSWORD"
require_hex_secret MUSIC_POSTGRES_PASSWORD "$MUSIC_POSTGRES_PASSWORD"
require_hex_secret CHATBOT_POSTGRES_PASSWORD "$CHATBOT_POSTGRES_PASSWORD"

for name in \
  POSTGRES_ADMIN_USER \
  MUSIC_POSTGRES_DB \
  MUSIC_POSTGRES_USER \
  CHATBOT_POSTGRES_DB \
  CHATBOT_POSTGRES_USER
do
  value="$(printenv "$name")"
  require_identifier "$name" "$value"
done

if [ "$MUSIC_POSTGRES_DB" = "$CHATBOT_POSTGRES_DB" ] \
  || [ "$MUSIC_POSTGRES_USER" = "$CHATBOT_POSTGRES_USER" ]; then
  printf '%s\n' "Music and Chatbot must use different databases and roles" >&2
  exit 1
fi

if [ "$POSTGRES_ADMIN_PASSWORD" = "$MUSIC_POSTGRES_PASSWORD" ] \
  || [ "$POSTGRES_ADMIN_PASSWORD" = "$CHATBOT_POSTGRES_PASSWORD" ] \
  || [ "$MUSIC_POSTGRES_PASSWORD" = "$CHATBOT_POSTGRES_PASSWORD" ] \
  || [ "$APP_SECRET" = "$POSTGRES_ADMIN_PASSWORD" ] \
  || [ "$APP_SECRET" = "$MUSIC_POSTGRES_PASSWORD" ] \
  || [ "$APP_SECRET" = "$CHATBOT_POSTGRES_PASSWORD" ]; then
  printf '%s\n' "Application and PostgreSQL secrets must all be different" >&2
  exit 1
fi

case "$AUDIO_SMTP_FROM_EMAIL" in
  *@*) ;;
  *)
    printf '%s\n' "AUDIO_SMTP_FROM_EMAIL must be an email address" >&2
    exit 1
    ;;
esac

if [ "$MUSIC_PORT" = "$CHATBOT_PORT" ]; then
  printf '%s\n' "MUSIC_PORT and CHATBOT_PORT must be different" >&2
  exit 1
fi

printf '%s\n' "Production preflight passed"
