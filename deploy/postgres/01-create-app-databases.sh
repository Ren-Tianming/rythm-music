#!/bin/sh
set -eu

psql \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  --set=music_db="$MUSIC_POSTGRES_DB" \
  --set=music_user="$MUSIC_POSTGRES_USER" \
  --set=music_password="$MUSIC_POSTGRES_PASSWORD" \
  --set=chatbot_db="$CHATBOT_POSTGRES_DB" \
  --set=chatbot_user="$CHATBOT_POSTGRES_USER" \
  --set=chatbot_password="$CHATBOT_POSTGRES_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'music_user', :'music_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'music_user') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'music_user', :'music_password') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'chatbot_user', :'chatbot_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'chatbot_user') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'chatbot_user', :'chatbot_password') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'music_db', :'music_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'music_db') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'chatbot_db', :'chatbot_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'chatbot_db') \gexec

SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'music_db') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'music_db', :'music_user') \gexec
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'chatbot_db') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'chatbot_db', :'chatbot_user') \gexec
EOSQL
