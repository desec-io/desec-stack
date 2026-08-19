"""
DNS transport: a minimal unbound-control client for our own recursive resolver,
plus a query helper for it.

Kept apart from desecapi.delegation so that the measurement logic there deals
with interpreting responses only.
"""

import socket

from django.conf import settings
import dns.flags, dns.message, dns.query


# unbound's remote control is a line protocol: send "UBCT1 <command>\n" and read
# the response, which is "ok" on success (send_ok() in daemon/remote.c) and
# "error <reason>" otherwise. The daemon reads the magic string with a single
# recv() of six bytes, so command and magic may be sent in one go.
CONTROL_MAGIC = "UBCT1 "
CONTROL_TIMEOUT = 5
QUERY_TIMEOUT = 10


class UnboundException(Exception):
    pass


class UnboundControlException(UnboundException):
    pass


class UnboundQueryException(UnboundException):
    pass


def _control(command):
    """
    Executes a command on the resolver's remote control channel and returns its
    response. Raises UnboundControlException if the command did not succeed.
    """
    address = (settings.UNBOUND_HOST, settings.UNBOUND_CONTROL_PORT)
    try:
        with socket.create_connection(address, timeout=CONTROL_TIMEOUT) as sock:
            sock.sendall(f"{CONTROL_MAGIC}{command}\n".encode())
            chunks = []
            while chunk := sock.recv(4096):
                chunks.append(chunk)
    except OSError as e:
        raise UnboundControlException(f"{command}: {e}") from e

    response = b"".join(chunks).decode(errors="replace")
    if response.partition("\n")[0].strip() != "ok":
        raise UnboundControlException(
            f"{command}: {response.strip() or '(no response)'}"
        )
    return response


def flush_delegation(name):
    """
    Makes the resolver forget everything it knows about the delegation of the
    given name, so that the next query resolves the zone cut from scratch.
    """
    _control(f"flush_delegation {name}")


def query(qname, rdtype, *, cd=False):
    """
    Sends a recursive, DNSSEC-enabled query to the resolver and returns the
    response. Raises dns.exception.Timeout if the resolver does not answer in
    time, and UnboundQueryException if it cannot be reached at all.

    :param cd: If given, ask for the answer without DNSSEC validation.
    """
    message = dns.message.make_query(qname, rdtype, want_dnssec=True)  # RD=1, DO=1
    if cd:
        message.flags |= dns.flags.CD
    try:
        # dnspython wants an address, not a name (and the resolver's address may
        # change when its container is recreated).
        where = socket.gethostbyname(settings.UNBOUND_HOST)
        response, _ = dns.query.udp_with_fallback(
            message, where, port=settings.UNBOUND_PORT, timeout=QUERY_TIMEOUT
        )
    except OSError as e:
        raise UnboundQueryException(f"{qname}: {e}") from e
    return response
