#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait-dbapi
./wait-ns

# start cron
/root/cronhook/start-cron.sh &

echo Starting API tests ...
coverage run manage.py test -v 3 --noinput --parallel auto
coverage combine
coverage report
