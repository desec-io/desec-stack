#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

ZONE=$1
PARENT=${ZONE#*.}
SALT=`head -c300 /dev/urandom | sha512sum | cut -b 1-16`

filename=/tmp/`date -Ins`_$ZONE.log
touch $filename
chmod 640 $filename

echo "signing $ZONE and updating serial"
pdnsutil secure-zone $ZONE && pdnsutil set-nsec3 $ZONE "1 0 10 $SALT" && pdnsutil increase-serial $ZONE || exit 2

echo "Setting DS records for $ZONE and put them in parent zone"
DATA='{"rrsets": [ {"name": "'"$ZONE".'", "type": "DS", "ttl": 60, "changetype": "REPLACE", "records": '
DATA+=`curl -sS -X GET -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/api/v1/servers/localhost/zones/$ZONE/cryptokeys \
	| jq -c '[.[] | select(.active == true) | {content: .ds[]?, disabled: false}]'`
DATA+=" } ] }"
echo $DATA >> $filename
curl -sSv -X PATCH --data "$DATA" -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/api/v1/servers/localhost/zones/$PARENT &>> $filename || exit 3

echo -n "This was $0: "
date
