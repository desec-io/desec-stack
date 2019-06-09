#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait

# start cron
# Start child process that starts grand-child process.
# After the child process's death, the grand-child will be adopted by init.
# See https://stackoverflow.com/a/20338327
( /root/cronhook/start-cron.sh & )

# migrate database
python manage.py migrate || exit 1

echo Finished migrations, starting API server ...
exec uwsgi --ini uwsgi.ini
