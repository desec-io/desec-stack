#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait

# start cron
/root/cronhook/start-cron.sh &

echo Starting API tests ...
python3 manage.py test -v 3 --noinput
