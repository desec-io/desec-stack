#!/bin/bash
envsubst < /etc/unbound/unbound.conf.d/resolver.conf.var > /etc/unbound/unbound.conf.d/resolver.conf
exec unbound
