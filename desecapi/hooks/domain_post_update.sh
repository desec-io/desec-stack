#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

ZONE=$1

echo "rectify, increase-serial, notify $ZONE"
pdnssec rectify-zone $ZONE && pdnssec increase-serial $ZONE && pdns_control notify $ZONE || exit 2

echo -n "This was $0: "
date
