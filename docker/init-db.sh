#!/bin/sh
set -eu

# The application owns only its database and never uses the bootstrap superuser.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set app_password="$SECUREVAULT_DB_PASSWORD" <<'SQL'
CREATE ROLE securevault LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE securevault OWNER securevault;
REVOKE ALL ON DATABASE securevault FROM PUBLIC;
SQL
