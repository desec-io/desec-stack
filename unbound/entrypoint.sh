#!/bin/bash -e

# Manage configuration via envsubst
export NPROC="$(nproc)"
envsubst < /opt/unbound/etc/unbound/unbound.conf.var > /opt/unbound/etc/unbound/unbound.conf

# Seed (or refresh) the root trust anchor. Exit code 1 means that the anchor was
# updated, which is not an error; if the network is unavailable, unbound-anchor
# writes the built-in anchor instead.
unbound-anchor -a /opt/unbound/var/root.key || true
chown unbound:unbound /opt/unbound/var /opt/unbound/var/root.key

unbound-checkconf /opt/unbound/etc/unbound/unbound.conf

exec unbound -d -c /opt/unbound/etc/unbound/unbound.conf
