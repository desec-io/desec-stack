#!/usr/bin/env bash
set -euo pipefail

# VPN routing (same as before)
/sbin/ip route add 10.8.0.0/24  via ${DESECSTACK_IPV4_REAR_PREFIX16}.7.2 || true
/sbin/ip route add 239.1.2.0/24 via ${DESECSTACK_IPV4_REAR_PREFIX16}.7.2 || true

# Fix UDP TTL (same workaround as before)
iptables -t mangle -A OUTPUT -p udp -j TTL --ttl-set 64 || true

# Inject environment variables into Knot config
envsubst < /etc/knot/knot.conf.var > /etc/knot/knot.conf
chown knot:knot /etc/knot/knot.conf

# Ensure storage and socket directories exist with correct ownership
mkdir -p /var/lib/knot /run/knot
chown -R knot:knot /var/lib/knot /run/knot
# 777 on the socket directory so the api container (different uid) can reach the socket.
# The socket itself is created world-accessible via umask 0 below.
chmod 777 /run/knot

# umask 0 is inherited by knotd, causing the control socket to be created with mode 0777,
# which allows the api container's process to connect without a shared GID.
umask 0
exec knotd -c /etc/knot/knot.conf
