#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

ZONE=$1

echo "rectify, increase-serial, notify $ZONE"

echo running: pdnsutil rectify-zone $ZONE
pdnsutil rectify-zone $ZONE || exit 2

echo running: pdnsutil increase-serial $ZONE
pdnsutil increase-serial $ZONE || exit 2

echo running: pdns_control notify $ZONE
pdns_control notify $ZONE || exit 2

echo -n "This was $0: "
date
