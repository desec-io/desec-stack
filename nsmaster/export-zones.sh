#!/usr/bin/env bash
# Export all zones from the PowerDNS nsmaster to /zones-export/
# Usage: docker compose exec nsmaster /root/export-zones.sh [output-dir]
set -euo pipefail

OUTPUT_DIR="${1:-/zones-export}"
mkdir -p "$OUTPUT_DIR"

echo "Fetching zone list via pdnsutil ..."
ZONE_COUNT=0

for ZONE in $(pdnsutil list-all-zones); do
    # Skip catalog.internal — Knot generates it automatically from its zone list
    [[ "$ZONE" == "catalog.internal." ]] && continue

    pdnsutil export-zone "$ZONE" > "$OUTPUT_DIR/${ZONE}zone"
    echo "$ZONE" >> "$OUTPUT_DIR/zone-list.txt"
    ZONE_COUNT=$((ZONE_COUNT + 1))
    echo "  Exported: $ZONE"
done

echo "Exported $ZONE_COUNT zones to $OUTPUT_DIR"
