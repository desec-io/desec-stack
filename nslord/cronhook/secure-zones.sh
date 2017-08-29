#!/bin/bash

APITOKEN=`pdns_control current-config | awk -F= -v key="api-key" '$1==key {print $2}'`

cd /root/cronhook

# Iterate over new zones (created with type NATIVE and without DNSSEC)
for ZONE in `echo "SELECT name FROM domains WHERE type = 'NATIVE' && id NOT IN(SELECT domain_id FROM cryptokeys WHERE active = 1);" | mysql --defaults-file=my.cnf -N`; do
	set -ex

	PARENT=${ZONE#*.}
	SALT=`head -c32 /dev/urandom | sha256sum | cut -b 1-16`

	# Set up DNSSEC, switch zone type to MASTER, and increase serial for notify
	pdnsutil secure-zone -- "$ZONE" \
		&& pdnsutil set-nsec3 -- "$ZONE" "1 0 300 $SALT" \
		&& pdnsutil set-kind -- "$ZONE" MASTER \
		&& pdnsutil increase-serial -- "$ZONE"

	# Take care of delegations
	if [ "$PARENT" == "dedyn.io" ]; then
		SUBNAME=${ZONE%%.*}

		set +x # don't write commands with sensitive information to the screen

		echo "Getting DS records for $ZONE and put them in parent zone"
		DATA='{"subname": "'"$SUBNAME"'", "type": "DS", "ttl": 60, "records": '
		DATA+=`curl -sS -X GET -H "X-API-Key: $APITOKEN" "http://nslord:8081/api/v1/servers/localhost/zones/$ZONE/cryptokeys" \
			| jq -c '[.[] | select(.active == true) | .ds[]?]'`
		DATA+=' }'
		curl -sS -X POST --data "$DATA" -H "Content-Type: application/json" http://api:8080/api/v1/domains/$PARENT/rrsets/
	fi
done
