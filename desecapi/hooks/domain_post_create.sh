#!/bin/bash
echo -n "This is $0: "
date

if [ -z "$1" ]; then
        exit 1
fi

ZONE=$1
PARENT=${ZONE#*.}
SALT=`head -c300 /dev/urandom | sha512sum | cut -b 1-16`

echo "sign, rectify, increase-serial, notify $ZONE"
pdnssec secure-zone $ZONE; pdnssec set-nsec3 $ZONE "1 0 10 $SALT" && `dirname $0`/domain_post_update.sh $ZONE || exit 2

echo "getting DS records for $ZONE"
IFS=$'\n'
DS=( $(pdnssec show-zone $ZONE | grep "^DS " | egrep -o "([0-9]+ ){3}[0-9a-fA-F]+") );

DATA='{"rrsets": [ {"name": "'"$ZONE"'", "type": "DS", "changetype": "REPLACE", "records": [ '
for (( i=0; i<=$(( ${#DS[*]} - 1 )); i++ )); do
        DATA+='{"content": "'"${DS[$i]}"'", "disabled": false, "name": "'"$ZONE"'", "ttl": 60, "type": "DS" }'
        if (($i < ${#DS[*]} - 1)); then
                DATA+=", "
        fi
done
DATA+=" ] } ] }"

echo $DATA | jq .

echo "Setting DS records in parent zone $PARENT (command follows)"
echo curl -X PATCH --data "$DATA" -H "X-API-Key: [secret]" http://127.0.0.1:8081/servers/localhost/zones/$PARENT
echo Output:
#curl -X PATCH --data "$DATA" -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/servers/localhost/zones/$PARENT || exit 3
curl -v -X PATCH --data "$DATA" -H "X-API-Key: $APITOKEN" http://127.0.0.1:8081/servers/localhost/zones/$PARENT &> /tmp/`date -Ins`_$ZONE.log || exit 3
echo

echo "rectify, increase-serial, notify $PARENT"
pdnssec rectify-zone $PARENT; pdnssec increase-serial $PARENT && pdns_control notify $PARENT || exit 4

echo -n "This was $0: "
date
