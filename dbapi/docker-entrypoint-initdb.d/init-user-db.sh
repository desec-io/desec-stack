#!/bin/bash
set -e

# Get the postgres user or set it to a default value
if [ -n $POSTGRES_USER ]; then pg_user=$POSTGRES_USER; else pg_user="postgres"; fi
# Get the postgres db or set it to a default value
if [ -n $POSTGRES_DB ]; then pg_db=$POSTGRES_DB; else pg_db=$POSTGRES_USER; fi

if [ -n "$POSTGRES_NON_ROOT_USER" ]; then
psql -v ON_ERROR_STOP=1 --username "$pg_user" --dbname "$pg_db" <<-EOSQL
    CREATE USER $POSTGRES_NON_ROOT_USER with encrypted password '$POSTGRES_NON_ROOT_USER_PASSWORD';
    GRANT CREATE, CONNECT ON DATABASE $pg_db TO $POSTGRES_NON_ROOT_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, UPDATE, INSERT, DELETE, REFERENCES ON TABLES TO $POSTGRES_NON_ROOT_USER;
EOSQL

if [[ "$DESECSTACK_API_TEST" == "TRUE" ]]; then
psql -v ON_ERROR_STOP=1 --username "$pg_user" <<-EOSQL
    ALTER USER $POSTGRES_NON_ROOT_USER CREATEDB;
EOSQL
fi

fi
