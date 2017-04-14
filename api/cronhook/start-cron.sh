#!/bin/sh
# start-cron.sh

printenv >> /etc/environment
touch /var/log/cron.log
cron
tail -F -v /var/log/cron.log
