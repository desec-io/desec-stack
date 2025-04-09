#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait-dbapi
./wait-ns

# start cron
/root/cronhook/start-cron.sh &

echo Starting API tests ...
coverage run --source='.' -m pytest
coverage report
