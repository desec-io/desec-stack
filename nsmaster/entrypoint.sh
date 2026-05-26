#!/bin/bash

# Route required for communicating with secondaries through VPN
/sbin/ip route add 10.8.0.0/24 via 172.16.7.2
/sbin/ip route add 239.1.2.0/24 via 172.16.7.2

# Fix UDP TTL which sometimes is one, causing packets intended for VPN clients to be dropped at the VPN server
# TODO remove this workaround once the problem has been solved at its root
iptables -t mangle -A OUTPUT -p udp -j TTL --ttl-set 64

# wait for dbmaster database to come up
until PGPASSWORD=$DESECSTACK_DBMASTER_PASSWORD_pdns psql -h dbmaster -U pdns -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# Manage credentials
envsubst < /etc/powerdns/pdns.conf.var > /etc/powerdns/pdns.conf

exec pdns_server --daemon=no
