import socket
import threading
from contextlib import contextmanager
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
import dns.edns, dns.exception, dns.flags, dns.message, dns.rcode, dns.rdatatype, dns.rrset

from desecapi import delegation, unbound
from desecapi.models import DelegationCheck, Domain, User


OUR_NS = ["ns1.example.net", "ns2.example.net"]
QNAME = "example.com."
PARENT = "com."
PARENT_NS = "a.gtld.example."


def make_response(
    qname=QNAME, *, rcode=dns.rcode.NOERROR, ad=False, answer=(), authority=(), ede=()
):
    query = dns.message.make_query(qname, dns.rdatatype.NS, want_dnssec=True)
    response = dns.message.make_response(query)
    response.set_rcode(rcode)
    if ad:
        response.flags |= dns.flags.AD
    response.answer.extend(answer)
    response.authority.extend(authority)
    response.use_edns(options=[dns.edns.EDEOption(*option) for option in ede])
    return response


def ns_rrset(*targets, name=QNAME):
    return dns.rrset.from_text(name, 3600, "IN", "NS", *targets)


def soa_rrset(name=PARENT):
    return dns.rrset.from_text(
        name, 3600, "IN", "SOA", f"ns1.{name} hostmaster.{name} 1 2 3 4 5"
    )


def rrsig_rrset(name=QNAME, *, covers="DS", signer=PARENT):
    return dns.rrset.from_text(
        name,
        3600,
        "IN",
        "RRSIG",
        f"{covers} 13 2 3600 20260401000000 20260101000000 12345 {signer} AAAA",
    )


def a_rrset(*addresses, name=PARENT_NS):
    return dns.rrset.from_text(name, 3600, "IN", "A", *addresses)


def _answer(item):
    if isinstance(item, BaseException):
        raise item
    return item


class DelegationCheckTestCase(SimpleTestCase):
    """
    Pins down the decision tables of desecapi.delegation: no resolver, no
    network, and (by way of SimpleTestCase) no database.
    """

    def check(
        self,
        *,
        ds=None,
        soa=None,
        parent_ns=None,
        addresses=None,
        delegation_=None,
        cds=None,
        dnskey=None,
        name="example.com",
        our_nameservers=OUR_NS,
    ):
        """
        Runs a check, answering each of its queries with the given response (or
        raising it, if it is an exception). The defaults describe example.com,
        securely delegated to our nameservers by a signed parent; a test states
        only the step it is about.

        `delegation_` may be a list with one item per parent nameserver, which
        are then made to exist.
        """
        if delegation_ is None:
            delegation_ = [make_response(authority=[ns_rrset(*OUR_NS)])]
        elif not isinstance(delegation_, list):
            delegation_ = [delegation_]
        if addresses is None:
            addresses = make_response(
                PARENT_NS,
                answer=[a_rrset(*(f"192.0.2.{i}" for i in range(len(delegation_))))],
            )

        responses = {
            # The parent is signed and says so, by signing its answer about the
            # DS (here: about there not being one).
            dns.rdatatype.DS: ds
            if ds is not None
            else make_response(authority=[rrsig_rrset()]),
            dns.rdatatype.SOA: soa
            if soa is not None
            else make_response(PARENT, answer=[soa_rrset()]),
            dns.rdatatype.NS: parent_ns
            if parent_ns is not None
            else make_response(PARENT, answer=[ns_rrset(PARENT_NS, name=PARENT)]),
            dns.rdatatype.A: addresses,
            dns.rdatatype.CDS: cds if cds is not None else make_response(ad=True),
            dns.rdatatype.DNSKEY: dnskey
            if dnskey is not None
            else make_response(PARENT, ad=True),
        }
        self.calls = []
        pending = list(delegation_)

        def flush(name):
            self.calls.append(("flush", name))

        def resolve(qname, rdtype, *, cd=False):
            self.calls.append(("query", qname.to_text(), dns.rdatatype.to_text(rdtype)))
            return _answer(responses[rdtype])

        def ask_server(address, qname, rdtype):
            self.calls.append(("query_server", address, qname.to_text()))
            return _answer(pending.pop(0))

        with (
            mock.patch("desecapi.unbound.flush_delegation", side_effect=flush),
            mock.patch("desecapi.unbound.query", side_effect=resolve),
            mock.patch("desecapi.delegation.query_server", side_effect=ask_server),
        ):
            return delegation.check(name, our_nameservers=our_nameservers)

    def assertStatus(self, result, security_status, nameserver_status):
        self.assertEqual(
            (result.security_status, result.nameserver_status),
            (security_status, nameserver_status),
        )

    @property
    def queried(self):
        return [call[1:] for call in self.calls if call[0] == "query"]

    @contextmanager
    def assertInconclusive(self, message):
        with self.assertLogs("desecapi", "ERROR") as logs:
            yield
        self.assertIn(message, "\n".join(logs.output))

    # Finding the parent (step 1)

    def test_parent_is_the_signer_of_the_ds_response(self):
        # The DS, and the denial of it, live in the parent zone and are signed
        # by it, so the signature names the zone cut -- no guessing.
        result = self.check(
            ds=make_response(answer=[rrsig_rrset(covers="DS", signer="com.")])
        )
        self.assertIn((PARENT, "NS"), self.queried)
        self.assertNotIn((PARENT, "SOA"), self.queried)
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.SECURE,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_parent_is_the_signer_of_a_denial(self):
        result = self.check(
            ds=make_response(authority=[rrsig_rrset(covers="NSEC3", signer="com.")])
        )
        self.assertIn((PARENT, "NS"), self.queried)
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_unsigned_parent_is_found_by_soa_and_settles_the_status(self):
        # No signature on the DS response: the parent is unsigned, so it cannot
        # carry a DS, and no further question about security needs asking.
        result = self.check(ds=make_response())
        self.assertIn((PARENT, "SOA"), self.queried)
        self.assertNotIn((QNAME, "CDS"), self.queried)
        self.assertNotIn((PARENT, "DNSKEY"), self.queried)
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.INSECURE,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_parent_is_the_soa_owner_not_the_stripped_name(self):
        # sub.example.com is inside example.com, so stripping one label lands
        # in the middle of a zone; the SOA in the response is what counts.
        self.check(
            name="sub.example.com",
            ds=make_response("sub.example.com."),
            soa=make_response(
                "example.com.",
                rcode=dns.rcode.NXDOMAIN,
                authority=[soa_rrset("example.com.")],
            ),
            parent_ns=make_response(
                "example.com.", answer=[ns_rrset(PARENT_NS, name="example.com.")]
            ),
            delegation_=make_response("sub.example.com.", rcode=dns.rcode.NXDOMAIN),
        )
        self.assertIn(("example.com.", "SOA"), self.queried)
        self.assertIn(("example.com.", "NS"), self.queried)

    def test_servfail_on_ds_is_misconfigured(self):
        result = self.check(
            ds=make_response(
                rcode=dns.rcode.SERVFAIL, ede=[(dns.edns.EDECode.DNSSEC_BOGUS, "bogus")]
            )
        )
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.MISCONFIGURED,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )
        self.assertEqual(result.ede_code, int(dns.edns.EDECode.DNSSEC_BOGUS))
        self.assertEqual(result.ede_text, "bogus")
        self.assertEqual(result.rcode, dns.rcode.SERVFAIL)

    def test_servfail_on_ds_without_dnssec_ede_is_error(self):
        result = self.check(
            ds=make_response(
                rcode=dns.rcode.SERVFAIL,
                ede=[(dns.edns.EDECode.NETWORK_ERROR, "network")],
            )
        )
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_parent_undetermined_without_soa(self):
        with self.assertInconclusive("no SOA for com."):
            result = self.check(ds=make_response(), soa=make_response(PARENT))
        # The parent is unsigned, which we know even without knowing its name.
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.INSECURE,
            DelegationCheck.NameserverStatus.ERROR,
        )

    def test_parent_undetermined_on_timeout(self):
        with self.assertInconclusive("no response to example.com. DS"):
            result = self.check(ds=dns.exception.Timeout())
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.ERROR,
        )
        self.assertIsNone(result.rcode)

    def test_parent_undetermined_on_refused(self):
        with self.assertInconclusive("example.com. DS: REFUSED"):
            result = self.check(ds=make_response(rcode=dns.rcode.REFUSED))
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.ERROR,
        )

    # Reading the delegation off the parent (steps 2 and 3)

    def test_delegation_is_read_from_the_parents_servers(self):
        self.check()
        self.assertEqual(
            [call for call in self.calls if call[0] == "query_server"],
            [("query_server", "192.0.2.0", QNAME)],
        )
        # The child's own idea of its NS RRset is never asked for.
        self.assertNotIn((QNAME, "NS"), self.queried)

    def test_correctly_delegated(self):
        result = self.check()
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )
        self.assertEqual(result.nameservers, ["ns1.example.net.", "ns2.example.net."])

    def test_correctly_delegated_with_subset_of_our_nameservers(self):
        result = self.check(
            delegation_=make_response(authority=[ns_rrset(OUR_NS[0])]),
        )
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )
        self.assertEqual(result.nameservers, ["ns1.example.net."])

    def test_multi_provider(self):
        result = self.check(
            delegation_=make_response(
                authority=[ns_rrset(OUR_NS[0], "ns1.other.example.")]
            )
        )
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.MULTI_PROVIDER
        )
        self.assertEqual(result.nameservers, ["ns1.example.net.", "ns1.other.example."])

    def test_other_provider(self):
        result = self.check(
            delegation_=make_response(
                authority=[ns_rrset("ns1.other.example.", "ns2.other.example.")]
            )
        )
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.OTHER_PROVIDER
        )

    def test_delegation_in_answer_section(self):
        # The parent's servers may be authoritative for the child as well, in
        # which case they answer instead of referring.
        result = self.check(delegation_=make_response(answer=[ns_rrset(*OUR_NS)]))
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_nameservers_are_normalized_and_deduplicated(self):
        result = self.check(
            delegation_=make_response(
                authority=[ns_rrset("NS2.Example.NET.", "ns2.example.net.")]
            )
        )
        self.assertEqual(result.nameservers, ["ns2.example.net."])

    def test_nameservers_of_other_names_are_ignored(self):
        result = self.check(
            delegation_=make_response(
                authority=[ns_rrset(*OUR_NS, name="other.example."), soa_rrset()]
            )
        )
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.NOT_DELEGATED
        )
        self.assertEqual(result.nameservers, [])

    def test_not_delegated_nxdomain(self):
        result = self.check(
            delegation_=make_response(
                rcode=dns.rcode.NXDOMAIN, authority=[soa_rrset()]
            ),
        )
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.NOT_DELEGATED
        )

    def test_not_delegated_nodata(self):
        result = self.check(delegation_=make_response(authority=[soa_rrset()]))
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.NOT_DELEGATED
        )

    def test_next_parent_server_is_asked_after_a_timeout(self):
        with self.assertLogs("desecapi", "WARNING"):
            result = self.check(
                delegation_=[
                    dns.exception.Timeout(),
                    make_response(authority=[ns_rrset(*OUR_NS)]),
                ]
            )
        self.assertEqual(
            [call[1] for call in self.calls if call[0] == "query_server"],
            ["192.0.2.0", "192.0.2.1"],
        )
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_next_parent_server_is_asked_after_a_servfail(self):
        with self.assertLogs("desecapi", "WARNING"):
            result = self.check(
                delegation_=[
                    make_response(rcode=dns.rcode.SERVFAIL),
                    make_response(authority=[ns_rrset(*OUR_NS)]),
                ]
            )
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_only_a_few_parent_servers_are_tried(self):
        # A parent that is unreachable must not cost one timeout per nameserver
        # -- TLDs have up to thirteen of them.
        with self.assertInconclusive("no usable answer"):
            self.check(
                parent_ns=make_response(
                    PARENT,
                    answer=[
                        ns_rrset(
                            *(f"ns{i}.gtld.example." for i in range(5)), name=PARENT
                        )
                    ],
                ),
                addresses=make_response(PARENT_NS, answer=[a_rrset("192.0.2.1")]),
                delegation_=[dns.exception.Timeout()] * 5,
            )
        self.assertEqual(
            len([call for call in self.calls if call[0] == "query_server"]),
            delegation.MAX_PARENT_SERVERS,
        )
        self.assertEqual(
            len([call for call in self.queried if call[1] == "A"]),
            delegation.MAX_PARENT_SERVERS,
        )

    def test_delegation_undetermined_when_no_server_answers(self):
        with self.assertInconclusive("no usable answer for example.com. NS"):
            result = self.check(delegation_=[dns.exception.Timeout()])
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.ERROR,
        )

    def test_delegation_undetermined_without_parent_nameservers(self):
        with self.assertInconclusive("no nameservers for com."):
            result = self.check(parent_ns=make_response(PARENT))
        self.assertEqual(
            result.nameserver_status, DelegationCheck.NameserverStatus.ERROR
        )

    def test_delegation_undetermined_without_parent_addresses(self):
        with self.assertInconclusive("no usable answer for example.com. NS"):
            self.check(addresses=make_response(PARENT_NS))

    def test_known_security_status_survives_an_undetermined_delegation(self):
        with self.assertInconclusive("no usable answer"):
            result = self.check(
                ds=make_response(), delegation_=[dns.exception.Timeout()]
            )
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.INSECURE,
            DelegationCheck.NameserverStatus.ERROR,
        )

    # Judging the delegation of a signed parent (step 4)

    def test_secure_delegation_is_read_from_a_record_below_the_cut(self):
        result = self.check(cds=make_response(ad=True))
        self.assertIn((QNAME, "CDS"), self.queried)
        self.assertNotIn((PARENT, "DNSKEY"), self.queried)
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.SECURE,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )
        self.assertEqual(result.rcode, dns.rcode.NOERROR)
        self.assertIsNone(result.ede_code)

    def test_insecure_delegation(self):
        result = self.check(cds=make_response(ad=False))
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.INSECURE,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_misconfigured_for_each_dnssec_ede(self):
        for code in sorted(delegation.DNSSEC_EDE_CODES):
            with self.subTest(ede_code=int(code)):
                result = self.check(
                    cds=make_response(rcode=dns.rcode.SERVFAIL, ede=[(code, "no luck")])
                )
                self.assertEqual(
                    result.security_status,
                    DelegationCheck.SecurityStatus.MISCONFIGURED,
                )
                self.assertEqual(result.ede_code, int(code))
                self.assertEqual(result.ede_text, "no luck")

    def test_error_for_other_ede(self):
        for code in (
            dns.edns.EDECode.NO_REACHABLE_AUTHORITY,  # 22
            dns.edns.EDECode.NETWORK_ERROR,  # 23
        ):
            with self.subTest(ede_code=int(code)):
                result = self.check(
                    cds=make_response(rcode=dns.rcode.SERVFAIL, ede=[(code, None)])
                )
                self.assertEqual(
                    result.security_status, DelegationCheck.SecurityStatus.ERROR
                )
                self.assertEqual(result.ede_code, int(code))
                self.assertEqual(result.ede_text, "")

    def test_error_for_servfail_without_ede(self):
        result = self.check(cds=make_response(rcode=dns.rcode.SERVFAIL))
        self.assertEqual(result.security_status, DelegationCheck.SecurityStatus.ERROR)
        self.assertIsNone(result.ede_code)

    def test_dnssec_ede_wins_over_others(self):
        result = self.check(
            cds=make_response(
                rcode=dns.rcode.SERVFAIL,
                ede=[
                    (dns.edns.EDECode.NETWORK_ERROR, "network"),
                    (dns.edns.EDECode.DNSSEC_BOGUS, "bogus"),
                ],
            )
        )
        self.assertEqual(
            result.security_status, DelegationCheck.SecurityStatus.MISCONFIGURED
        )
        self.assertEqual(result.ede_code, int(dns.edns.EDECode.DNSSEC_BOGUS))

    def test_security_undetermined_on_refused(self):
        with self.assertInconclusive("example.com. CDS: REFUSED"):
            result = self.check(cds=make_response(rcode=dns.rcode.REFUSED))
        # Only the security dimension is in doubt; the delegation is not.
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.ERROR,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )

    def test_security_undetermined_on_timeout(self):
        with self.assertInconclusive("no response to example.com. CDS"):
            result = self.check(cds=dns.exception.Timeout())
        self.assertEqual(result.security_status, DelegationCheck.SecurityStatus.ERROR)
        self.assertIsNone(result.rcode)

    def test_undelegated_name_is_secure_below_a_signed_parent(self):
        # The parent's denial of the name cannot be used for this: under NSEC3
        # opt-out it comes back insecure however well the parent is signed. So
        # the parent's own DNSKEY is what gets validated.
        result = self.check(
            delegation_=make_response(
                rcode=dns.rcode.NXDOMAIN, authority=[soa_rrset()]
            ),
            dnskey=make_response(PARENT, ad=True),
        )
        self.assertIn((PARENT, "DNSKEY"), self.queried)
        self.assertNotIn((QNAME, "CDS"), self.queried)
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.SECURE,
            DelegationCheck.NameserverStatus.NOT_DELEGATED,
        )

    def test_undelegated_name_is_insecure_below_an_unsigned_parent(self):
        result = self.check(
            delegation_=make_response(
                rcode=dns.rcode.NXDOMAIN, authority=[soa_rrset()]
            ),
            dnskey=make_response(PARENT, ad=False),
        )
        self.assertStatus(
            result,
            DelegationCheck.SecurityStatus.INSECURE,
            DelegationCheck.NameserverStatus.NOT_DELEGATED,
        )

    # Queries made

    def test_cache_is_flushed_before_querying(self):
        self.check()
        self.assertEqual(self.calls[0], ("flush", QNAME))
        self.assertEqual(len([call for call in self.calls if call[0] == "flush"]), 1)

    def test_control_channel_failure_propagates(self):
        with mock.patch(
            "desecapi.unbound.flush_delegation",
            side_effect=unbound.UnboundControlException("nope"),
        ):
            with self.assertRaises(unbound.UnboundControlException):
                delegation.check("example.com", our_nameservers=OUR_NS)

    def test_unreachable_resolver_propagates(self):
        with self.assertRaises(unbound.UnboundQueryException):
            self.check(ds=unbound.UnboundQueryException("nope"))

    @override_settings(DEFAULT_NS=["ns1.example.net."])
    def test_our_nameservers_default_to_setting(self):
        result = self.check(
            delegation_=make_response(authority=[ns_rrset("ns1.example.net.")]),
            our_nameservers=None,
        )
        self.assertEqual(
            result.nameserver_status,
            DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
        )


class UnboundControlTestCase(SimpleTestCase):
    """
    Exercises the unbound-control client against a socket speaking the UBCT1
    handshake.
    """

    @contextmanager
    def server(self, response=b"ok\n"):
        received = []
        listener = socket.create_server(("127.0.0.1", 0))

        def serve():
            try:
                connection, _ = listener.accept()
            except OSError:  # listener closed without a connection
                return
            with connection:
                received.append(connection.recv(4096))
                connection.sendall(response)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with override_settings(
                UNBOUND_HOST="127.0.0.1",
                UNBOUND_CONTROL_PORT=listener.getsockname()[1],
            ):
                yield received
        finally:
            listener.close()
            thread.join(timeout=5)

    def test_command(self):
        with self.server() as received:
            unbound.flush_delegation("example.com.")
        self.assertEqual(received, [b"UBCT1 flush_delegation example.com.\n"])

    def test_error_response(self):
        with self.server(response=b"error unknown command\n"):
            with self.assertRaisesMessage(
                unbound.UnboundControlException, "error unknown command"
            ):
                unbound.flush_delegation("example.com.")

    def test_empty_response(self):
        with self.server(response=b""):
            with self.assertRaises(unbound.UnboundControlException):
                unbound.flush_delegation("example.com.")

    def test_unreachable(self):
        # Claim a port, then release it so that nothing listens on it.
        with socket.create_server(("127.0.0.1", 0)) as listener:
            port = listener.getsockname()[1]
        with override_settings(UNBOUND_HOST="127.0.0.1", UNBOUND_CONTROL_PORT=port):
            with self.assertRaises(unbound.UnboundControlException):
                unbound.flush_delegation("example.com.")


class DelegationCheckModelTestCase(TestCase):
    """
    The check history is a change log: identical outcomes update the existing
    row's confirmation time, changed ones start a new row.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )
        cls.domain = Domain.objects.create(name="example.com", owner=cls.user)

    @staticmethod
    def result(**kwargs):
        kwargs.setdefault("security_status", DelegationCheck.SecurityStatus.SECURE)
        kwargs.setdefault(
            "nameserver_status", DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED
        )
        kwargs.setdefault("nameservers", ["ns1.example.net."])
        return delegation.DelegationCheckResult(**kwargs)

    def test_first_check_is_recorded_and_becomes_current(self):
        check = DelegationCheck.objects.record(self.domain, self.result(rcode=0))
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.current_delegation_check, check)
        self.assertEqual(check.security_status, DelegationCheck.SecurityStatus.SECURE)
        self.assertEqual(check.nameservers, ["ns1.example.net."])
        self.assertEqual(check.rcode, 0)
        self.assertEqual(check.ede_text, "")
        self.assertIsNone(check.ede_code)

    def test_unchanged_outcome_only_bumps_checked(self):
        check = DelegationCheck.objects.record(self.domain, self.result())
        self.domain.refresh_from_db()
        again = DelegationCheck.objects.record(self.domain, self.result())

        self.assertEqual(again.pk, check.pk)
        self.assertEqual(self.domain.delegation_checks.count(), 1)
        self.assertEqual(again.created, check.created)
        self.assertGreater(again.checked, check.checked)

    def test_unchanged_outcome_with_new_ede_only_bumps_checked(self):
        check = DelegationCheck.objects.record(self.domain, self.result(ede_code=6))
        self.domain.refresh_from_db()
        again = DelegationCheck.objects.record(
            self.domain, self.result(ede_code=7, ede_text="later")
        )
        self.assertEqual(again.pk, check.pk)
        self.assertEqual(again.ede_code, 6)  # not part of the recorded state

    def test_changed_outcome_starts_a_new_row(self):
        check = DelegationCheck.objects.record(self.domain, self.result())
        self.domain.refresh_from_db()
        changed = DelegationCheck.objects.record(
            self.domain,
            self.result(security_status=DelegationCheck.SecurityStatus.MISCONFIGURED),
        )
        self.domain.refresh_from_db()

        self.assertNotEqual(changed.pk, check.pk)
        self.assertEqual(self.domain.delegation_checks.count(), 2)
        self.assertEqual(self.domain.current_delegation_check, changed)

    def test_changed_nameservers_start_a_new_row(self):
        DelegationCheck.objects.record(self.domain, self.result())
        self.domain.refresh_from_db()
        DelegationCheck.objects.record(
            self.domain,
            self.result(nameservers=["ns1.example.net.", "ns2.example.net."]),
        )
        self.assertEqual(self.domain.delegation_checks.count(), 2)

    def test_history_survives_and_is_cleared_from_domain_on_deletion(self):
        check = DelegationCheck.objects.record(self.domain, self.result())
        self.domain.refresh_from_db()
        check.delete()
        self.domain.refresh_from_db()
        self.assertIsNone(self.domain.current_delegation_check)

    def test_checks_are_deleted_with_their_domain(self):
        DelegationCheck.objects.record(self.domain, self.result())
        self.domain.refresh_from_db()
        self.domain.delete()
        self.assertFalse(DelegationCheck.objects.exists())
