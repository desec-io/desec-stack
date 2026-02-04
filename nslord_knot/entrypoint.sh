#!/usr/bin/env bash

set -euo pipefail

envsubst < /etc/knot/knot.conf.var > /etc/knot/knot.conf
cp /etc/knot/catalog.zone.var /var/lib/knot/catalog.zone
chown -R knot:knot /var/lib/knot

knotc conf-import -f /etc/knot/knot.conf +nopurge

/usr/local/bin/catalog-watch.sh &

exec knotd
