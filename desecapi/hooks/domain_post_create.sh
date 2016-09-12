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

echo "sign, post-update $ZONE"
pdnsutil secure-zone $ZONE; pdnsutil set-nsec3 $ZONE "1 0 10 $SALT" && `dirname $0`/domain_post_update.sh $ZONE || exit 2

echo "getting DS records for $ZONE"
DATA='{"rrsets": [ {"name": "'"$ZONE".'", "type": "DS", "ttl": 60, "changetype": "REPLACE", "records": '
DATA+=`curl -sS -X GET -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/api/v1/servers/localhost/zones/$ZONE/cryptokeys \
	| jq -c '[.[] | select(.active == true) | {content: .ds[]?, disabled: false}]'`
DATA+=" } ] }"
echo $DATA >> $filename

echo "Setting DS records in parent zone $PARENT"
curl -sSv -X PATCH --data "$DATA" -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/api/v1/servers/localhost/zones/$PARENT &>> $filename || exit 3

echo "post-update $PARENT"
`dirname $0`/domain_post_update.sh $PARENT || exit 4

echo -n "This was $0: "
date
