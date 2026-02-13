#!/usr/bin/env bash

set -euo pipefail

envsubst < /etc/knot/knot.conf.var > /etc/knot/knot.conf
cp /etc/knot/catalog.zone.var /var/lib/knot/catalog.zone
chown -R knot:knot /var/lib/knot
mkdir -p /knot-import
chmod 0777 /knot-import

python3 /usr/local/bin/zone_watch.py &

exec knotd -c /etc/knot/knot.conf
