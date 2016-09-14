#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

set -ex

ZONE=$1

pdnsutil rectify-zone $ZONE
pdnsutil increase-serial $ZONE

pdns_control notify $ZONE
#dig -b 178.63.189.78 +short +opcode=NOTIFY SOA $ZONE @54.88.76.245
#dig -b 178.63.189.78 +short +opcode=NOTIFY SOA $ZONE @178.63.189.72

echo -n "This was $0: "
date
