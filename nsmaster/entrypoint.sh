#!/bin/bash

# Route required for communicating with secondaries through VPN
/sbin/ip route add 10.8.0.0/24 via 172.16.7.2
/sbin/ip route add 239.1.2.0/24 via 172.16.7.2

# Fix UDP TTL which sometimes is one, causing packets intended for VPN clients to be dropped at the VPN server
# TODO remove this workaround once the problem has been solved at its root
iptables -t mangle -A OUTPUT -p udp -j TTL --ttl-set 64

host=dbmaster-legacy; port=3306; n=120; i=0; while ! (echo > /dev/tcp/$host/$port) 2> /dev/null; do [[ $i -eq $n ]] && >&2 echo "$host:$port not up after $n seconds, exiting" && exit 1; echo "waiting for $host:$port to come up"; sleep 1; i=$((i+1)); done
# wait for dbmaster database to come up
until PGPASSWORD=$DESECSTACK_DBMASTER_PASSWORD_pdns psql -h dbmaster -U pdns -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# Manage credentials
envsubst < /etc/powerdns/pdns.conf.var > /etc/powerdns/pdns.conf
envsubst < /etc/powerdns/pdns-migrate.conf.var > /etc/powerdns/pdns-migrate.conf

# Migrate
pdnsutil --config-name migrate b2b-migrate gmysql gpgsql
pdnsutil rectify-all-zones

echo "Provisioning default TSIG key ..."
pdnsutil import-tsig-key default hmac-sha256 "${DESECSTACK_NSMASTER_TSIGKEY}" > /dev/null

exec pdns_server --daemon=no
