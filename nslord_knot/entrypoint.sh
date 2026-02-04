#!/usr/bin/env bash

set -euo pipefail

envsubst < /etc/knot/knot.conf.var > /etc/knot/knot.conf
if [ -z "${DESECSTACK_NSLORD_KNOT_UPDATE_KEY_SECRET:-}" ]; then
  awk '
    $0 ~ /^  - id: nslord-update$/ {skip=1; next}
    skip && $0 ~ /^  - id: / {skip=0}
    !skip {print}
  ' /etc/knot/knot.conf > /etc/knot/knot.conf.tmp
  mv /etc/knot/knot.conf.tmp /etc/knot/knot.conf
  sed -i '/key: nslord-update/d' /etc/knot/knot.conf
fi
cp /etc/knot/catalog.zone.var /var/lib/knot/catalog.zone
chown -R knot:knot /var/lib/knot

knotc conf-import -f /etc/knot/knot.conf +nopurge

/usr/local/bin/catalog-watch.sh &

exec knotd
