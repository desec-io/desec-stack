#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait

# start cron
/root/cronhook/start-cron.sh &

# migrate database
python manage.py migrate || exit 1

echo Finished migrations, starting API server ...
uwsgi --ini uwsgi.ini
