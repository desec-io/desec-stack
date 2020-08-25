#!/bin/sh
# start-cron.sh

printenv >> /etc/environment
touch /var/log/cron.log
crond -b -L /var/log/cron.log
tail -F -v /var/log/cron.log
