#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait-dbapi
./wait-ns

# set permissions for Django metrics (docker-compose.yml setting does not work, see #333)
chmod 1777 /var/local/django_metrics

# start cron
# Start child process that starts grand-child process.
# After the child process's death, the grand-child will be adopted by init.
# See https://stackoverflow.com/a/20338327
( /root/cronhook/start-cron.sh & )

# migrate database
python manage.py migrate || exit 1

# Prepare catalog zone
python manage.py align-catalog-zone

echo Starting API server ...
exec uwsgi --ini uwsgi.ini
