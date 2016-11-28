#!/bin/bash

host=dbmaster; port=3306; n=120; i=0; while ! (echo > /dev/tcp/$host/$port) 2> /dev/null; do [[ $i -eq $n ]] && >&2 echo "$host:$port not up after $n seconds, exiting" && exit 1; echo "waiting for $host:$port to come up"; sleep 1; i=$((i+1)); done

# Manage credentials
envsubst < /etc/powerdns/pdns.conf.var > /etc/powerdns/pdns.conf

pdns_server --daemon=no
