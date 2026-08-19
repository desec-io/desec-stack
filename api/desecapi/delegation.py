"""
Delegation and DS configuration checks.

For a given name, we determine two independent things: which nameservers it is
delegated to, and whether that delegation is DNSSEC-secured. The nameservers are
read from the *parent* side of the delegation, which is what a resolver follows
and what the registry publishes; a resolver cannot supply it, as it answers NS
queries from the child. The security verdict, in turn, is read off a validating
resolver's response instead of being recomputed here.

Measuring is kept apart from recording: a check returns a plain result object
and touches no database. What that result means is defined by DelegationCheck,
which is where the two status vocabularies live.
"""

import itertools
import random
from dataclasses import dataclass, field

from django.conf import settings
import dns.edns, dns.exception, dns.flags, dns.name, dns.rcode, dns.rdatatype

from desecapi import logger, unbound
from desecapi.dns import query_server
from desecapi.models import DelegationCheck


# EDE codes (RFC 8914) that tell us a SERVFAIL is about DNSSEC, i.e. that the
# delegation is broken -- as opposed to us being unable to check it. Everything
# else (22 No Reachable Authority, 23 Network Error, ...) is an error on our end
# as far as this check is concerned.
DNSSEC_EDE_CODES = frozenset(
    {
        dns.edns.EDECode.DNSSEC_INDETERMINATE,  # 5
        dns.edns.EDECode.DNSSEC_BOGUS,  # 6
        dns.edns.EDECode.SIGNATURE_EXPIRED,  # 7
        dns.edns.EDECode.SIGNATURE_NOT_YET_VALID,  # 8
        dns.edns.EDECode.DNSKEY_MISSING,  # 9
        dns.edns.EDECode.RRSIGS_MISSING,  # 10
        dns.edns.EDECode.NO_ZONE_KEY_BIT_SET,  # 11
        dns.edns.EDECode.NSEC_MISSING,  # 12
    }
)

# Response codes that state something about the name, as opposed to stating that
# the query failed. NXDOMAIN is one of them: it is how a parent says that a name
# is not delegated.
CONCLUSIVE_RCODES = frozenset({dns.rcode.NOERROR, dns.rcode.NXDOMAIN})

# How many of the parent's nameservers to try. Enough to survive one of them
# being down, few enough that a domain whose parent is unreachable costs seconds
# rather than minutes -- TLDs have up to thirteen.
MAX_PARENT_SERVERS = 3


@dataclass(frozen=True)
class DelegationCheckResult:
    """
    Outcome of a check. Field names match those of the DelegationCheck model.
    The rcode and EDE fields describe the response that settled the security
    status, which is the one worth keeping when something is wrong.
    """

    security_status: DelegationCheck.SecurityStatus
    nameserver_status: DelegationCheck.NameserverStatus
    nameservers: list[str] = field(default_factory=list)
    ede_code: int | None = None
    ede_text: str = ""
    rcode: int | None = None


class _Undetermined(Exception):
    """
    Raised when the check cannot be carried out, e.g. because the parent zone or
    the delegation could not be determined. Carries a short category of what went
    wrong, for the log, and the security status if it happens to be known anyway.
    """

    def __init__(self, reason, message, security_status=None):
        super().__init__(message)
        self.reason = reason
        self.security_status = security_status


def check(name, *, our_nameservers=None):
    """
    Determines the delegation security status and the nameserver status of the
    given name.

    Raises UnboundException if our resolver could not be operated (as opposed to
    the name being unresolvable, which is a legitimate outcome).
    """
    if our_nameservers is None:
        our_nameservers = settings.DEFAULT_NS
    our_nameservers = {_normalize(ns) for ns in our_nameservers}

    try:
        return _check(dns.name.from_text(name), our_nameservers)
    except _Undetermined as e:
        logger.error(
            "Delegation check for %s is inconclusive (%s): %s", name, e.reason, e
        )
        return DelegationCheckResult(
            e.security_status or DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.ERROR,
        )


def _check(qname, our_nameservers):
    # Flush before querying, not after: the check is then independent of
    # anything that happened earlier, including a crash during a previous one.
    unbound.flush_delegation(qname.to_text())

    parent, security_status, security_response = _find_parent(qname)

    try:
        nameservers = _extract_nameservers(_query_delegation(qname, parent), qname)
    except _Undetermined as e:
        e.security_status = security_status
        raise

    if security_status is None:
        security_status, security_response = _classify_security(
            qname, parent, nameservers
        )

    ede_code, ede_text = _extract_ede(security_response)
    return DelegationCheckResult(
        security_status=security_status,
        nameserver_status=_classify_nameservers(nameservers, our_nameservers),
        nameservers=nameservers,
        ede_code=ede_code,
        ede_text=ede_text,
        rcode=security_response.rcode() if security_response else None,
    )


def _find_parent(qname):
    """
    Returns the parent zone of the given name, the delegation security status if
    it already follows from how the parent answered, and the response it was
    read from.

    The parent is where both the delegation and the DS live. It is not simply
    the name with one label stripped, as the zone cut can be further up -- but a
    signed parent names itself: the DS RRset, and the proof that there is none,
    are served and signed by the parent, so its name is the signer. An unsigned
    parent cannot carry a DS, which settles the security status right here.
    """
    try:
        response = unbound.query(qname, rdtype=dns.rdatatype.DS)
    except dns.exception.Timeout:
        raise _Undetermined("parent", f"no response to {qname} DS")

    rcode = response.rcode()
    if rcode in CONCLUSIVE_RCODES:
        signer = _extract_signer(response)
        if signer is not None:
            return signer, None, response
        security_status = DelegationCheck.SecurityStatus.INSECURE
    elif rcode == dns.rcode.SERVFAIL:
        # The chain of trust is broken above the name, so nothing below it can
        # be secure. Which of the two it is, the EDE tells us.
        ede_code, _ = _extract_ede(response)
        security_status = (
            DelegationCheck.SecurityStatus.MISCONFIGURED
            if ede_code in DNSSEC_EDE_CODES
            else DelegationCheck.SecurityStatus.ERROR
        )
    else:
        raise _Undetermined("parent", f"{qname} DS: {dns.rcode.to_text(rcode)}")

    try:
        return _find_zone(qname), security_status, response
    except _Undetermined as e:
        e.security_status = security_status
        raise


def _find_zone(qname):
    """
    Returns the closest zone above the given name, read off the SOA record that
    authoritative servers include in an answer about a name they serve.
    """
    try:
        parent = qname.parent()
    except dns.name.NoParent:
        raise _Undetermined("parent", f"{qname} has no parent")

    try:
        # Without validation: we are locating a zone cut, not judging it, and
        # the reason we are here may well be that validation fails.
        response = unbound.query(parent, rdtype=dns.rdatatype.SOA, cd=True)
    except dns.exception.Timeout:
        raise _Undetermined("parent", f"no response to {parent} SOA")

    for section in (response.answer, response.authority):
        for rrset in section:
            if rrset.rdtype == dns.rdatatype.SOA:
                return rrset.name
    raise _Undetermined("parent", f"no SOA for {parent}")


def _query_delegation(qname, parent):
    """
    Returns the parent's response to an NS query for the given name, i.e. the
    delegation as the parent publishes it.

    Asked non-recursively, and of the parent's servers in turn: a server that
    does not answer says nothing about the delegation, so we move on to the
    next one -- but only up to MAX_PARENT_SERVERS of them, so that an
    unreachable parent costs a bounded amount of time.
    """
    for address in itertools.islice(_parent_addresses(parent), MAX_PARENT_SERVERS):
        try:
            response = query_server(address, qname, dns.rdatatype.NS)
        except (dns.exception.DNSException, OSError) as e:
            logger.warning("%s did not answer for %s NS: %s", address, qname, e)
            continue
        if response.rcode() in CONCLUSIVE_RCODES:
            return response
        logger.warning(
            "%s answered %s for %s NS",
            address,
            dns.rcode.to_text(response.rcode()),
            qname,
        )
    raise _Undetermined("delegation", f"no usable answer for {qname} NS from {parent}")


def _parent_addresses(parent):
    """
    Yields the addresses of some of the parent's nameservers, resolving them one
    at a time: usually, the first one answers. Which ones is left to chance, so
    that a bulk run spreads over a TLD's servers instead of asking the
    alphabetically first one about every domain.
    """
    try:
        response = unbound.query(parent, rdtype=dns.rdatatype.NS)
    except dns.exception.Timeout:
        raise _Undetermined("delegation", f"no response to {parent} NS")

    nameservers = _extract_nameservers(response, parent)
    if not nameservers:
        raise _Undetermined("delegation", f"no nameservers for {parent}")

    for nameserver in random.sample(
        nameservers, min(len(nameservers), MAX_PARENT_SERVERS)
    ):
        try:
            response = unbound.query(
                dns.name.from_text(nameserver), rdtype=dns.rdatatype.A
            )
        except dns.exception.Timeout:
            continue
        for rrset in response.answer:
            if rrset.rdtype == dns.rdatatype.A:
                yield from (rr.address for rr in rrset)


def _classify_security(qname, parent, nameservers):
    """
    Determines whether a delegation from a signed parent is secured, by asking
    our resolver something whose validation covers the delegation, and reading
    its verdict off the AD bit. Returns the status and the response it is from.
    """
    if nameservers:
        # There is a delegation, so ask for a record in the child zone: getting
        # there validates the whole chain, DS included. CDS specifically,
        # because comparing what the child publishes there against the parent's
        # DS is the natural next thing to check -- and then this response is
        # already at hand.
        name, rdtype = qname, dns.rdatatype.CDS
    else:
        # There is no delegation to ask below, so the question becomes whether
        # the parent is signed, i.e. whether this name could be secured at all
        # once it is delegated. Its own denial of existence cannot answer that:
        # a parent using NSEC3 opt-out cannot prove the non-existence of an
        # unsigned name, so the denial comes back insecure however well the
        # parent itself is signed.
        name, rdtype = parent, dns.rdatatype.DNSKEY

    try:
        response = unbound.query(name, rdtype=rdtype)
    except dns.exception.Timeout:
        return _security_undetermined(f"no response to {name} {rdtype.name}"), None

    rcode = response.rcode()
    if rcode in CONCLUSIVE_RCODES:
        security_status = (
            DelegationCheck.SecurityStatus.SECURE
            if response.flags & dns.flags.AD
            else DelegationCheck.SecurityStatus.INSECURE
        )
    elif rcode == dns.rcode.SERVFAIL:
        ede_code, _ = _extract_ede(response)
        security_status = (
            DelegationCheck.SecurityStatus.MISCONFIGURED
            if ede_code in DNSSEC_EDE_CODES
            else DelegationCheck.SecurityStatus.ERROR
        )
    else:
        security_status = _security_undetermined(
            f"{name} {rdtype.name}: {dns.rcode.to_text(rcode)}"
        )
    return security_status, response


def _security_undetermined(message):
    logger.error("Delegation security status is inconclusive: %s", message)
    return DelegationCheck.SecurityStatus.ERROR


def _extract_signer(response):
    """
    Returns the zone that signed the response, or None if it carries no
    signature at all.
    """
    for section in (response.answer, response.authority):
        for rrset in section:
            if rrset.rdtype == dns.rdatatype.RRSIG:
                return next(iter(rrset)).signer
    return None


def _extract_nameservers(response, qname):
    """
    Returns the NS owner names seen for qname, lowercased and absolute. In a
    referral they are in the authority section, in an answer from the zone
    itself in the answer section.
    """
    for section in (response.answer, response.authority):
        for rrset in section:
            if rrset.rdtype == dns.rdatatype.NS and rrset.name == qname:
                return sorted({_normalize(rr.target) for rr in rrset})
    return []


def _classify_nameservers(nameservers, our_nameservers):
    if not nameservers:
        return DelegationCheck.NameserverStatus.NOT_DELEGATED
    # The raw set is stored alongside, so incomplete delegations (a subset of
    # ours, but not all of them) can be analyzed later without a schema change.
    if set(nameservers) <= our_nameservers:
        return DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED
    if set(nameservers) & our_nameservers:
        # TODO Inspect the DNSSEC configuration in more detail. Multi-signer
        # setups need per-provider DNSKEY/DS analysis, which the AD bit alone
        # cannot express.
        return DelegationCheck.NameserverStatus.MULTI_PROVIDER
    return DelegationCheck.NameserverStatus.OTHER_PROVIDER


def _extract_ede(response):
    if response is None:
        return None, ""
    options = [
        option
        for option in response.options
        if option.otype == dns.edns.OptionType.EDE  # type: ignore[attr-defined]
    ]
    # A response may carry several EDE options; if the delegation is broken,
    # that's the one which explains the SERVFAIL.
    option = next(
        (option for option in options if option.code in DNSSEC_EDE_CODES),
        next(iter(options), None),
    )
    if option is None:
        return None, ""
    return int(option.code), option.text or ""


def _normalize(name):
    return dns.name.from_text(str(name)).to_text().lower()
