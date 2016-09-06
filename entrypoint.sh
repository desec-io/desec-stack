#!/bin/bash

host=db; port=3306; n=120; i=0; while ! (echo > /dev/tcp/$host/$port) 2> /dev/null; do [[ $i -eq $n ]] && >&2 echo "$host:$port not up after $n seconds, exiting" && exit 1; echo "waiting for $host:$port to come up"; sleep 1; i=$((i+1)); done
host=ns; port=8081; n=120; i=0; while ! (echo > /dev/tcp/$host/$port) 2> /dev/null; do [[ $i -eq $n ]] && >&2 echo "$host:$port not up after $n seconds, exiting" && exit 1; echo "waiting for $host:$port to come up"; sleep 1; i=$((i+1)); done

python manage.py migrate

echo Finished migrations, starting API server ...
python manage.py runserver 0.0.0.0:8000
