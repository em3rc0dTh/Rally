#!/usr/bin/env bash
# Runs only when Docker creates a NEW PostgreSQL data volume.
# Do not assume that an existing volume has been upgraded.
set -euo pipefail
: "$POSTGRES_DB"
: "$POSTGRES_USER"
: "$RALLY_APP_PASSWORD"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set ON_ERROR_STOP=1 --set app_password="$RALLY_APP_PASSWORD" \
  --set db_name="$POSTGRES_DB" <<'SQL'
SELECT format(
  'CREATE ROLE rally_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
  :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rally_app')
\gexec
SELECT format('ALTER DATABASE %I OWNER TO rally_app', :'db_name')
\gexec
SQL
