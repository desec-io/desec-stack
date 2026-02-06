#!/bin/bash -e

# wait for dependencies
echo "waiting for dependencies ..."
./wait-dbapi
./wait-ns

# start cron
/root/cronhook/start-cron.sh &

echo Starting API tests ...
test_labels=()
if [[ -n "${DESEC_TEST_LABELS:-}" ]]; then
  read -r -a test_labels <<< "${DESEC_TEST_LABELS}"
fi
coverage run --source='.' manage.py test -v 3 --noinput "${test_labels[@]}"
coverage report
