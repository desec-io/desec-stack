#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

set -ex

ZONE=$1

pdnsutil rectify-zone $ZONE

echo -n "This was $0: "
date
