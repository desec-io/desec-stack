#!/bin/sh
# start-cron.sh

touch /var/log/cron.log
cron
tail -F -v /var/log/cron.log
