#!/usr/bin/env bash
set -Eeo pipefail

# This password is set for the postgres user when initializing the database. It is not needed and thus not printed.
export POSTGRES_PASSWORD=$(pwgen -1 -s 32)
/usr/local/bin/docker-entrypoint.sh "$@"
