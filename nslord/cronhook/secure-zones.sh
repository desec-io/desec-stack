#!/bin/bash

APITOKEN=`pdns_control current-config | awk -F= -v key="api-key" '$1==key {print $2}'`

cd /root/cronhook

for ZONE in `echo "SELECT name FROM domains WHERE type = 'NATIVE' && id NOT IN(SELECT domain_id FROM cryptokeys WHERE active = 1);" | mysql --defaults-file=my.cnf -N`; do
	set -ex

	PARENT=${ZONE#*.}
	SALT=`head -c300 /dev/urandom | sha512sum | cut -b 1-16`
	pdnsutil secure-zone $ZONE && pdnsutil set-nsec3 $ZONE "1 0 300 $SALT" && pdnsutil set-kind $ZONE MASTER

	if [ "$PARENT" == "dedyn.io" ]; then
		set +x # don't write commands with sensitive information to the screen

		echo "Setting DS records for $ZONE and put them in parent zone"
		DATA='{"rrsets": [ {"name": "'"$ZONE".'", "type": "DS", "ttl": 60, "changetype": "REPLACE", "records": '
		DATA+=`curl -sS -X GET -H "X-API-Key: $APITOKEN" http://nslord:8081/api/v1/servers/localhost/zones/$ZONE/cryptokeys \
			| jq -c '[.[] | select(.active == true) | {content: .ds[]?, disabled: false}]'`
		DATA+=" } ] }"
		curl -sSv -X PATCH --data "$DATA" -H "X-API-Key: $APITOKEN" http://nslord:8081/api/v1/servers/localhost/zones/$PARENT
	fi
done
