#!/bin/bash
mkdir -p /dev/net
mknod /dev/net/tun c 10 200
openvpn --config /etc/openvpn/server.conf
