#!/bin/sh
if ! test -f /etc/ssh/keys/ssh_host_ed25519_key; then
  ssh-keygen -t ed25519 -f /etc/ssh/keys/ssh_host_ed25519_key
fi
touch /etc/ssh/keys/git_authorized_keys
exec /usr/sbin/sshd -D -e  # -D to not daemonize, -e to log to stdout/stderr
