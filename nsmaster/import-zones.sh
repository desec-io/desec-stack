#!/usr/bin/env bash
# Import zones exported from PowerDNS into Knot DNS (config DB mode)
# Usage: docker compose exec nsmaster /root/import-zones.sh [input-dir]
set -euo pipefail

INPUT_DIR="${1:-/zones-export}"
ZONE_DIR="/var/lib/knot/zones"

if [[ ! -f "$INPUT_DIR/zone-list.txt" ]]; then
    echo "ERROR: $INPUT_DIR/zone-list.txt not found" >&2
    exit 1
fi

mkdir -p "$ZONE_DIR"
chown knot:knot "$ZONE_DIR"

echo "Registering zones in Knot config DB ..."

# Open a single transaction for all zones for efficiency
knotc conf-begin

while IFS= read -r ZONE; do
    [[ -z "$ZONE" ]] && continue

    # Pre-load zone file so Knot does not have to AXFR every zone from nslord on first start
    cp "$INPUT_DIR/${ZONE}zone" "$ZONE_DIR/${ZONE}zone"
    chown knot:knot "$ZONE_DIR/${ZONE}zone"

    knotc conf-set "zone[$ZONE]"
    knotc conf-set "zone[$ZONE].template" "slave"
    knotc conf-set "zone[$ZONE].file" "$ZONE_DIR/${ZONE}zone"

    echo "  Registered: $ZONE"
done < "$INPUT_DIR/zone-list.txt"

knotc conf-commit

echo "Reloading all zones ..."
knotc zone-reload

echo "Import complete."
