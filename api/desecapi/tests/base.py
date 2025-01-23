import base64
import operator
import random
import re
import responses
import socket
import string
from contextlib import nullcontext
from functools import partial, reduce
from unittest import mock

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import mail
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework.utils import json

from desecapi.models import User, Domain, Token, RRset, RR
from desecapi.models.domains import psl
from desecapi.models.records import (
    RR_SET_TYPES_AUTOMATIC,
    RR_SET_TYPES_UNSUPPORTED,
    RR_SET_TYPES_MANAGEABLE,
)
from .matchers import body_matcher


class DesecAPIClient(APIClient):
    @staticmethod
    def _http_header_base64_conversion(content):
        return base64.b64encode(content.encode()).decode()

    def set_credentials(self, authorization):
        self.credentials(HTTP_AUTHORIZATION=authorization)

    def set_credentials_basic_auth(self, part_1, part_2=None):
        if not part_1 and not part_2:
            self.set_credentials("")
        else:
            s = part_1 if not part_2 else "%s:%s" % (part_1, part_2)
            self.set_credentials("Basic " + self._http_header_base64_conversion(s))

    def set_credentials_token_auth(self, token):
        if token is None:
            self.set_credentials("")
        else:
            self.set_credentials("Token " + token)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reverse = DesecTestCase.reverse

    def bulk_patch_rr_sets(self, domain_name, payload):
        return self.patch(
            self.reverse("v1:rrsets", name=domain_name),
            payload,
        )

    def bulk_post_rr_sets(self, domain_name, payload):
        return self.post(
            self.reverse("v1:rrsets", name=domain_name),
            payload,
        )

    def bulk_put_rr_sets(self, domain_name, payload):
        return self.put(
            self.reverse("v1:rrsets", name=domain_name),
            payload,
        )

    def post_rr_set(self, domain_name, **kwargs):
        data = kwargs or None
        if data:
            data.setdefault("ttl", 60)
        return self.post(
            self.reverse("v1:rrsets", name=domain_name),
            data=data,
        )

    def get_rr_sets(self, domain_name, **kwargs):
        return self.get(
            self.reverse("v1:rrsets", name=domain_name) + kwargs.pop("query", ""),
            kwargs,
        )

    def get_rr_set(self, domain_name, subname, type_):
        return self.get(
            self.reverse("v1:rrset@", name=domain_name, subname=subname, type=type_)
        )

    def put_rr_set(self, domain_name, subname, type_, data):
        return self.put(
            self.reverse("v1:rrset@", name=domain_name, subname=subname, type=type_),
            data,
        )

    def patch_rr_set(self, domain_name, subname, type_, data):
        return self.patch(
            self.reverse("v1:rrset@", name=domain_name, subname=subname, type=type_),
            data,
        )

    def delete_rr_set(self, domain_name, subname, type_):
        return self.delete(
            self.reverse("v1:rrset@", name=domain_name, subname=subname, type=type_)
        )

    # TODO add and use {post,get,delete,...}_domain


class AssertRequestsContextManager:
    """
    Checks that in its context, certain expected requests are made.
    """

    @classmethod
    def _flatten_nested_lists(cls, l):
        for i in l:
            if isinstance(i, list) or isinstance(i, tuple):
                yield from cls._flatten_nested_lists(i)
            else:
                yield i

    def __init__(
        self,
        test_case,
        expected_requests,
        single_expectation_single_request=True,
        expect_order=True,
    ):
        """
        Initialize a context that checks for made HTTP requests.

        Args:
            test_case: Test case in which this context lives. Used to fail test if observed requests do not meet
            expectations.
            expected_requests: (Possibly nested) list of requests, represented by kwarg-dictionaries for
            `responses.add`.
            single_expectation_single_request: If True (default), each expected request needs to be matched by exactly
            one observed request.
            expect_order: If True (default), requests made are expected in order of expectations given.
        """
        self.test_case = test_case
        self.expected_requests = list(self._flatten_nested_lists(expected_requests))
        self.single_expectation_single_request = single_expectation_single_request
        self.expect_order = expect_order

    def __enter__(self):
        self.test_case.responses.reset()
        for request in self.expected_requests:
            if "callback" in request:
                self.test_case.responses.add_callback(**request)
            else:
                self.test_case.responses.add(**request)
        # Used in pdns module
        self._gethostbyname, socket.gethostbyname = (
            socket.gethostbyname,
            lambda host: "127.0.0.1",
        )

    @staticmethod
    def _find_matching_request(pattern, requests):
        for request in requests:
            if pattern["method"] == request[0] and pattern["url"].match(request[1]):
                if pattern.get("payload") and pattern["payload"] not in request[2]:
                    continue
                return request
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        # organize seen requests in a primitive data structure
        seen_requests = [
            (r.method, r.url, r.body) for r, _ in self.test_case.responses.calls
        ]
        unmatched_requests = seen_requests[:]

        # go through expected requests one by one
        requests_to_check = list(self.expected_requests)[:]
        while requests_to_check:
            request = requests_to_check.pop(0)

            # match request
            match = None
            if self.expect_order:
                if not self.single_expectation_single_request:
                    raise ValueError(
                        "Checking of multiple (possibly zero) requests per expectation and checking of request "
                        "order simultaneously is not implemented, sorry."
                    )
                if unmatched_requests:
                    match = self._find_matching_request(
                        request, [unmatched_requests[0]]
                    )
            else:
                match = self._find_matching_request(
                    request,
                    (
                        unmatched_requests
                        if self.single_expectation_single_request
                        else seen_requests
                    ),
                )

            # check match
            if not match and self.single_expectation_single_request:
                self.test_case.fail(
                    (
                        "Expected to see a %s request on\n\n%s,\n\nbut only saw these %i "
                        "requests:\n\n%s\n\nAll expected requests:\n\n%s\n\n"
                        "Hint: check for possible duplicates in your expectation.\n"
                        + (
                            "Hint: Is the expectation order correct?"
                            if self.expect_order
                            else ""
                        )
                    )
                    % (
                        request["method"],
                        request["url"],
                        len(seen_requests),
                        "\n".join(map(str, seen_requests)),
                        "\n".join(
                            map(
                                str,
                                [
                                    (r["method"], r["url"])
                                    for r in self.expected_requests
                                ],
                            )
                        ),
                    )
                )
            if match:
                unmatched_requests.remove(match)

        # see if any requests were unexpected
        if unmatched_requests and self.single_expectation_single_request:
            self.test_case.fail(
                "While waiting for %i request(s), we saw %i unexpected request(s). The unexpected "
                "request(s) was/were:\n\n%s\n\nAll recorded requests:\n\n%s\n\nAll expected requests:"
                "\n\n%s"
                % (
                    len(self.expected_requests),
                    len(unmatched_requests),
                    "\n".join(map(str, unmatched_requests)),
                    "\n".join(map(str, seen_requests)),
                    "\n".join(
                        map(
                            str,
                            [(r["method"], r["url"]) for r in self.expected_requests],
                        )
                    ),
                )
            )
        socket.gethostbyname = self._gethostbyname


class MockPDNSTestCase(APITestCase):
    """
    This test case provides a "mocked Internet" environment with a mock pdns API interface. All internet connections,
    HTTP or otherwise, that this test case is unaware of will result in an exception.

    By default, requests are intercepted but unexpected will result in a failed test. To set pdns API request
    expectations, use the `with MockPDNSTestCase.assertPdns*` context managers.
    """

    PDNS_ZONES = r"/zones\?rrsets=false"
    PDNS_ZONE_CRYPTO_KEYS = r"/zones/(?P<id>[^/]+)/cryptokeys"
    PDNS_ZONE = r"/zones/(?P<id>[^/]+)"
    PDNS_ZONE_AXFR = r"/zones/(?P<id>[^/]+)/axfr-retrieve"
    PDNS_ZONE_EXPORT = r"/zones/(?P<id>[^/]+)/export"
    PCH_ZONE_CREATE = r"/zones"
    PCH_ZONE_DELETE = r"/zones"

    @classmethod
    def get_full_pdns_url(cls, path_regex, ns="LORD", **kwargs):
        api = getattr(settings, "NS%s_PDNS_API" % ns)
        return re.compile("^" + api + cls.fill_regex_groups(path_regex, **kwargs) + "$")

    @classmethod
    def fill_regex_groups(cls, template, **kwargs):
        s = template
        for name, value in kwargs.items():
            if value is None:
                continue
            pattern = r"\(\?P\<%s\>[^\)]+\)" % name
            if not re.search(pattern, s):
                raise ValueError(
                    "Tried to fill field %s in template %s, but it does not exist."
                    % (name, template)
                )
            s = re.sub(
                pattern=pattern,
                repl=value,
                string=s,
            )

        return s

    @classmethod
    def _pdns_zone_id_heuristic(cls, name):
        """
        Returns an educated guess of the pdns zone id for a given zone name.
        """
        if not name:
            return None

        name = cls._normalize_name(name)

        return name.translate(
            str.maketrans({"/": "=2F", "_": "=5F"})
        )  # make sure =5F is not lower-cased

    @classmethod
    def _normalize_name(cls, arg):
        if not arg:
            return None

        if not isinstance(arg, list):
            return cls._normalize_name([arg])[0]
        else:
            return [x.rstrip(".") + "." for x in arg]

    @classmethod
    def request_pdns_zone_create(cls, ns, *match):
        return {
            "method": "POST",
            "url": cls.get_full_pdns_url(cls.PDNS_ZONES, ns=ns),
            "status": 201,
            "body": "",
            "match": match,
        }

    @classmethod
    def request_pdns_zone_create_422(cls):
        request = cls.request_pdns_zone_create(ns="LORD")
        request["status"] = 422
        return request

    @classmethod
    def request_pdns_zone_delete(cls, name=None, ns="LORD"):
        return {
            "method": "DELETE",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE, ns=ns, id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": "",
        }

    @classmethod
    def request_pdns_zone_update(cls, name=None):
        return {
            "method": "PATCH",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE, id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": "",
        }

    def request_pdns_zone_update_assert_body(
        self, name: str = None, updated_rr_sets: list[RRset] | dict = None
    ):
        if updated_rr_sets is None:
            updated_rr_sets = []

        def request_callback(request):
            if not updated_rr_sets:
                # nothing to assert
                return [200, {}, ""]

            body = json.loads(request.body)
            self.assertTrue(
                "rrsets" in body.keys(),
                "pdns zone update request malformed: did not contain a list of RR sets.",
            )

            try:  # if an assertion fails, an exception is raised. We want to send a reply anyway!
                # convert updated_rr_sets into a plain data type, if Django models were given
                if isinstance(updated_rr_sets, list):
                    updated_rr_sets_dict = {}
                    for rr_set in updated_rr_sets:
                        updated_rr_sets_dict[
                            (rr_set.type, rr_set.subname, rr_set.ttl)
                        ] = rrs = []
                        for rr in rr_set.records.all():
                            rrs.append(rr.content)
                elif isinstance(updated_rr_sets, dict):
                    updated_rr_sets_dict = updated_rr_sets
                else:
                    raise ValueError(
                        "updated_rr_sets must be a list of RRSets or a dict."
                    )

                # check expectations
                self.assertEqual(
                    len(updated_rr_sets_dict),
                    len(body["rrsets"]),
                    "Saw an unexpected number of RR set updates: expected %i, intercepted %i."
                    % (len(updated_rr_sets_dict), len(body["rrsets"])),
                )
                for (
                    exp_type,
                    exp_subname,
                    exp_ttl,
                ), exp_records in updated_rr_sets_dict.items():
                    expected_name = ".".join(filter(None, [exp_subname, name])) + "."
                    for seen_rr_set in body["rrsets"]:
                        if (
                            expected_name == seen_rr_set["name"]
                            and exp_type == seen_rr_set["type"]
                        ):
                            # TODO replace the following asserts by assertTTL, assertRecords, ... or similar
                            if len(exp_records):
                                self.assertEqual(exp_ttl, seen_rr_set["ttl"])
                            self.assertEqual(
                                set(exp_records),
                                set([rr["content"] for rr in seen_rr_set["records"]]),
                            )
                            break
                    else:
                        # we did not break out, i.e. we did not find a matching RR set in body['rrsets']
                        self.fail(
                            "Expected to see an pdns zone update request for RR set of domain `%s` with name "
                            "`%s` and type `%s`, but did not see one. Seen update request on %s for RR sets:"
                            "\n\n%s"
                            % (
                                name,
                                expected_name,
                                exp_type,
                                request["url"],
                                json.dumps(body["rrsets"], indent=4),
                            )
                        )
            finally:
                return [200, {}, ""]

        request = self.request_pdns_zone_update(name)
        request.pop("status")
        request.pop("body")
        request["callback"] = request_callback
        return request

    @classmethod
    def request_pdns_zone_retrieve(cls, name=None):
        return {
            "method": "GET",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE, id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": json.dumps(
                {
                    "rrsets": [
                        {
                            "comments": [],
                            "name": cls._normalize_name(name) if name else "test.mock.",
                            "ttl": 60,
                            "type": "NS",
                            "records": [{"content": ns} for ns in settings.DEFAULT_NS],
                        }
                    ]
                }
            ),
        }

    @staticmethod
    def get_body_pdns_zone_retrieve_crypto_keys():
        common_body = {
            "algorithm": "ECDSAP256SHA256",
            "bits": 256,
            "dnskey": "257 3 13 EVBcsqrnOp6RGWtsrr9QW8cUtt/WI5C81RcCZDTGNI9elAiMQlxRdnic+7V+b7jJDE2vgY08qAbxiNh5NdzkzA==",
            "id": 179425943,
            "published": True,
            "type": "Cryptokey",
        }
        common_cds = [
            "62745 13 2 5cddaeaa383e2ea7de49bd1212bf520228f0e3b334626517e5f6a68eb85b48f6",
            "62745 13 4 b3f2565901ddcb0b78337301cf863d1045774377bca05c7ad69e17a167734b929f0a49b7edcca913eb6f5dfeac4645b8",
        ]
        return [
            {
                **common_body,
                "flags": 257,
                "keytype": "csk",
                "cds": common_cds,
            },
            {
                **common_body,
                "flags": 257,
                "keytype": "ksk",
                "cds": common_cds,
            },
            {
                **common_body,
                "flags": 256,
                "keytype": "zsk",
            },
        ]

    @classmethod
    def request_pdns_zone_retrieve_zone_export(cls, name=None):
        return {
            "method": "GET",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE_EXPORT, id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": "Zone export dummy!",
        }

    @classmethod
    def request_pdns_zone_retrieve_crypto_keys(cls, name=None):
        return {
            "method": "GET",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE_CRYPTO_KEYS, id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": json.dumps(cls.get_body_pdns_zone_retrieve_crypto_keys()),
        }

    @classmethod
    def request_pdns_zone_axfr(cls, name=None):
        return {
            "method": "PUT",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE_AXFR, ns="MASTER", id=cls._pdns_zone_id_heuristic(name)
            ),
            "status": 200,
            "body": "",
        }

    @classmethod
    def request_pdns_update_catalog(cls):
        return {
            "method": "PATCH",
            "url": cls.get_full_pdns_url(
                cls.PDNS_ZONE,
                ns="MASTER",
                id=cls._pdns_zone_id_heuristic("catalog.internal"),
            ),
            "status": 204,
            "body": "",
        }

    def request_pch_zone_create(self, name):
        def request_callback(request):
            try:
                self.assertEqual(
                    request.body,
                    {"zones": [name]},
                    f"Expected PCH zone creation request for {name}, but got '{request.body}'.",
                )
            finally:
                return [
                    201,
                    {},
                    json.dumps(
                        {
                            "status": True,
                            "message": "Zone(s) ADDED",
                            "zones": [name],
                        }
                    ),
                ]

        return {
            "method": "POST",
            "url": re.compile("^" + settings.PCH_API + self.PCH_ZONE_CREATE),
            "callback": request_callback,
        }

    def request_pch_zone_delete(self, name):
        def request_callback(request):
            try:
                self.assertEqual(
                    request.body,
                    {"zones": [name]},
                    f"Expected PCH zone deletion request for {name}, but got '{request.body}'.",
                )
            finally:
                return [
                    200,
                    {},
                    json.dumps(
                        {
                            "status": True,
                            "message": "Zone(s) deleted",
                            "zones": [name],
                        }
                    ),
                ]

        return {
            "method": "DELETE",
            "url": re.compile("^" + settings.PCH_API + self.PCH_ZONE_DELETE),
            "callback": request_callback,
        }

    def assertRequests(self, *expected_requests, expect_order=True):
        """
        Assert the given requests are made. To build requests, use the `MockPDNSTestCase.request_*` functions.
        Unmet expectations will fail the test.
        Args:
            *expected_requests: List of expected requests.
            expect_order: If True (default), the order of observed requests is checked.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=expected_requests,
            expect_order=expect_order,
        )

    def assertNoRequestsBut(self, *expected_requests):
        """
        Assert no requests other than the given ones are made. Each request can be matched more than once, unmatched
        expectations WILL NOT fail the test.
        Args:
            *expected_requests: List of acceptable requests to be made.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=expected_requests,
            single_expectation_single_request=False,
            expect_order=False,
        )

    def assertZoneCreation(self, name):
        """
        Asserts that nslord, nsmaster and PCH are contacted for zone creation.
        Name is only asserted for requests to PCH.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=[
                self.request_pdns_zone_create(ns="LORD"),
                self.request_pdns_zone_create(ns="MASTER"),
                self.request_pch_zone_create(name=name),
            ],
        )

    def assertZoneDeletion(self, name):
        """
        Asserts that nslord, nsmaster and PCH are contacted for zone deletion.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=[
                self.request_pdns_zone_delete(ns="LORD", name=name),
                self.request_pdns_zone_delete(ns="MASTER", name=name),
                self.request_pch_zone_delete(name=name),
            ],
        )

    def assertStatus(self, response, status):
        if response.status_code != status:
            self.fail(
                (
                    "Expected a response with status %i, but saw response with status %i. "
                    + (
                        "\n@@@@@ THE REQUEST CAUSING THIS RESPONSE WAS UNEXPECTED BY THE TEST @@@@@\n"
                        if response.status_code == 599
                        else ""
                    )
                    + "The response was %s.\n"
                    "The response body was\n\n%s"
                )
                % (
                    status,
                    response.status_code,
                    response,
                    (
                        str(response.data).replace("\\n", "\n")
                        if hasattr(response, "data")
                        else ""
                    ),
                )
            )

    def assertResponse(self, response, code=None, body=None):
        if code:
            self.assertStatus(response, code)
        if body:
            self.assertJSONEqual(response.content, body)

    def assertToken(self, plain, owner=None):
        owner = owner or self.owner
        self.assertTrue(
            any(
                check_password(plain, hashed, preferred="pbkdf2_sha256_iter1")
                for hashed in Token.objects.filter(owner=owner).values_list(
                    "key", flat=True
                )
            )
        )
        self.assertEqual(len(Token.make_hash(plain).split("$")), 4)

    def tearDown(self):
        super().tearDown()
        try:
            self.responses.stop()
        finally:
            self.responses.reset()

    def setUp(self):
        super().setUp()
        self.responses = responses.RequestsMock(assert_all_requests_are_fired=False)
        self.responses.start()
        for request in [
            # TODO delete not in this list - is this even needed?
            self.request_pdns_zone_create(ns="LORD"),
            self.request_pdns_zone_create(ns="MASTER"),
            self.request_pdns_zone_axfr(),
            self.request_pdns_zone_update(),
            self.request_pdns_zone_retrieve_crypto_keys(),
            self.request_pdns_zone_retrieve(),
        ]:
            if "callback" in request:
                self.responses.add_callback(**request)
            else:
                self.responses.add(**request)


class DesecTestCase(MockPDNSTestCase):
    """
    This test case is run in the "standard" deSEC e.V. setting, i.e. with an API that is aware of the public suffix
    domains AUTO_DELEGATION_DOMAINS.

    The test case aims to be as close to the deployment as possible and may be extended as the deployment evolves.

    The test case provides an admin user and a regular user for testing.
    """

    client_class = DesecAPIClient

    AUTO_DELEGATION_DOMAINS = settings.LOCAL_PUBLIC_SUFFIXES
    PUBLIC_SUFFIXES = {
        "de",
        "com",
        "io",
        "gov.cd",
        "edu.ec",
        "xxx",
        "pinb.gov.pl",
        "valer.ostfold.no",
        "kota.aichi.jp",
        "s3.amazonaws.com",
        "wildcard.ck",
    }
    SUPPORTED_RR_SET_TYPES = {
        "A",
        "AAAA",
        "AFSDB",
        "APL",
        "CAA",
        "CDNSKEY",
        "CDS",
        "CERT",
        "CNAME",
        "CSYNC",
        "DHCID",
        "DNAME",
        "DNSKEY",
        "DLV",
        "DS",
        "EUI48",
        "EUI64",
        "HINFO",
        "HTTPS",
        "KX",
        "L32",
        "L64",
        "LOC",
        "LP",
        "MX",
        "NAPTR",
        "NID",
        "NS",
        "OPENPGPKEY",
        "PTR",
        "RP",
        "SMIMEA",
        "SPF",
        "SRV",
        "SSHFP",
        "SVCB",
        "TLSA",
        "TXT",
        "URI",
    }

    admin = None
    auto_delegation_domains = None
    user = None

    @classmethod
    def reverse(cls, view_name, **kwargs):
        return reverse(view_name, kwargs=kwargs)

    def setUp(self):
        super().setUp()
        random.seed(0xDE5EC)
        self.admin = self.create_user(is_admin=True)
        self.auto_delegation_domains = [
            self.create_domain(name=name) for name in self.AUTO_DELEGATION_DOMAINS
        ]
        self.user = self.create_user()

    @classmethod
    def random_string(cls, length=6, chars=string.ascii_letters + string.digits):
        return "".join(random.choice(chars) for _ in range(length))

    @classmethod
    def random_password(cls, length=12):
        return cls.random_string(
            length,
            chars=string.ascii_letters
            + string.digits
            + string.punctuation
            + 'some 💩🐬 UTF-8: “红色联合”对“四·二八兵团”总部大楼的攻击已持续了两天"',
        )

    @classmethod
    def random_ip(cls, proto=None):
        proto = proto or random.choice([4, 6])
        if proto == 4:
            return ".".join([str(random.randrange(256)) for _ in range(4)])
        elif proto == 6:
            return "2001:" + ":".join(
                ["%x" % random.randrange(16**4) for _ in range(7)]
            )
        else:
            raise ValueError(
                "Unknown IP protocol version %s. Expected int 4 or int 6." % str(proto)
            )

    @classmethod
    def random_username(cls, host=None):
        host = host or cls.random_domain_name(cls.PUBLIC_SUFFIXES)
        return cls.random_string() + "+test@" + host.lower()

    @classmethod
    def random_domain_name(cls, suffix=None):
        if not suffix:
            suffix = cls.PUBLIC_SUFFIXES
        if isinstance(suffix, set):
            suffix = random.sample(list(suffix), 1)[0]
        return (
            random.choice(string.ascii_letters)
            + cls.random_string()
            + "--test"
            + "."
            + suffix
        ).lower()

    @classmethod
    def has_local_suffix(cls, domain_name: str):
        return any(
            [
                domain_name.endswith(f".{suffix}")
                for suffix in settings.LOCAL_PUBLIC_SUFFIXES
            ]
        )

    @classmethod
    def create_token(cls, owner, **kwargs):
        return Token.objects.create(owner=owner, **kwargs)

    @classmethod
    def create_user(cls, needs_captcha=False, **kwargs):
        kwargs.setdefault("email", cls.random_username())
        user = User(needs_captcha=needs_captcha, **kwargs)
        user.plain_password = cls.random_string(length=12)
        user.set_password(user.plain_password)
        user.save()
        return user

    @classmethod
    def create_domain(cls, suffix=None, **kwargs):
        kwargs.setdefault("owner", cls.create_user())
        kwargs.setdefault("name", cls.random_domain_name(suffix))
        domain = Domain(**kwargs)
        domain.save()
        return domain

    @classmethod
    def create_rr_set(cls, domain, records, **kwargs):
        if isinstance(domain, str):
            domain = Domain.objects.get(name=domain)
            domain.save()
        rr_set = RRset(domain=domain, **kwargs)
        rr_set.save()
        for r in records:
            RR(content=r, rrset=rr_set).save()
        return rr_set

    @classmethod
    def _find_auto_delegation_zone(cls, name):
        if not name:
            return None
        parents = [
            parent
            for parent in cls.AUTO_DELEGATION_DOMAINS
            if name.endswith("." + parent)
        ]
        if not parents:
            raise ValueError(
                "Could not find auto delegation zone for zone %s; searched in %s"
                % (name, cls.AUTO_DELEGATION_DOMAINS)
            )
        return parents[0]

    def requests_desec_domain_creation(self, name=None, axfr=True, keys=True):
        soa_content = "get.desec.io. get.desec.io. 1 86400 3600 2419200 3600"
        requests = [
            self.request_pdns_zone_create("LORD", body_matcher(soa_content)),
            self.request_pdns_zone_create(ns="MASTER"),
            self.request_pdns_update_catalog(),
            self.request_pch_zone_create(name=name),
        ]
        if axfr:
            requests.append(self.request_pdns_zone_axfr(name=name))
        if keys:
            requests.append(self.request_pdns_zone_retrieve_crypto_keys(name=name))
        return requests

    def requests_desec_domain_deletion(self, domain):
        requests = [
            self.request_pdns_zone_delete(name=domain.name, ns="LORD"),
            self.request_pdns_zone_delete(name=domain.name, ns="MASTER"),
            self.request_pdns_update_catalog(),
            self.request_pch_zone_delete(name=domain.name),
        ]

        if domain.is_locally_registrable:
            delegate_at = self._find_auto_delegation_zone(domain.name)
            requests += [
                self.request_pdns_zone_update(name=delegate_at),
                self.request_pdns_zone_axfr(name=delegate_at),
            ]

        return requests

    def requests_desec_domain_creation_auto_delegation(self, name=None):
        delegate_at = self._find_auto_delegation_zone(name)
        return self.requests_desec_domain_creation(name=name) + [
            self.request_pdns_zone_update(name=delegate_at),
            self.request_pdns_zone_axfr(name=delegate_at),
        ]

    @classmethod
    def requests_desec_rr_sets_update(cls, name=None):
        return [
            cls.request_pdns_zone_update(name=name),
            cls.request_pdns_zone_axfr(name=name),
        ]

    def assertBadRequest(self, response, message, path=()):
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            reduce(lambda obj, key: obj.__getitem__(key), path, response.data), message
        )

    def assertRRSet(
        self, response_rr, domain=None, subname=None, records=None, type_=None, **kwargs
    ):
        kwargs["domain"] = domain
        kwargs["subname"] = subname
        kwargs["records"] = records
        kwargs["type"] = type_

        for key, value in kwargs.items():
            if value is not None:
                self.assertEqual(
                    response_rr[key],
                    value,
                    'RR set did not have the expected %s: Expected "%s" but was "%s" in %s'
                    % (key, value, response_rr[key], response_rr),
                )

    def assertRRsetDB(
        self,
        domain: Domain,
        subname: str,
        type_: str,
        ttl: int = None,
        rr_contents: set[str] = None,
    ):
        if rr_contents is not None:
            try:
                has_rr_contents = {
                    rr.content
                    for rr in domain.rrset_set.get(
                        subname=subname, type=type_
                    ).records.all()
                }
            except RRset.DoesNotExist:
                has_rr_contents = set()
            self.assertSetEqual(
                has_rr_contents,
                rr_contents,
                f'{domain.name}: RRset for subname="{subname}" and type={type_} did not have the expected records '
                f"{rr_contents}, but had {has_rr_contents}.",
            )
        if ttl is not None:
            has_ttl = domain.rrset_set.get(subname=subname, type=type_).ttl
            self.assertEqual(
                has_ttl,
                ttl,
                f'{domain.name}: RRset for subname="{subname}" and type={type_} did not '
                f"have the expected TTL of {ttl}, but had {has_ttl}.",
            )

    @staticmethod
    def _count_occurrences_by_mask(rr_sets, masks):
        def _cmp(key, a, b):
            if key == "records":
                a = sorted(a)
                b = sorted(b)
            return a == b

        def _filter_rr_sets_by_mask(rr_sets_, mask):
            return [
                rr_set
                for rr_set in rr_sets_
                if reduce(
                    operator.and_,
                    [
                        _cmp(key, rr_set.get(key, None), value)
                        for key, value in mask.items()
                    ],
                )
            ]

        return [len(_filter_rr_sets_by_mask(rr_sets, mask)) for mask in masks]

    def assertRRSetsCount(self, rr_sets, masks, count=1):
        actual_counts = self._count_occurrences_by_mask(rr_sets, masks)
        if not all([actual_count == count for actual_count in actual_counts]):
            self.fail(
                "Expected to find %i RR set(s) for each of %s, but distribution is %s in %s."
                % (count, masks, actual_counts, rr_sets)
            )

    def assertContainsRRSets(self, rr_sets_haystack, rr_sets_needle):
        if not all(self._count_occurrences_by_mask(rr_sets_haystack, rr_sets_needle)):
            self.fail(
                "Expected to find RR sets with %s, but only got %s."
                % (rr_sets_needle, rr_sets_haystack)
            )

    def assertContains(
        self, response, text, count=None, status_code=200, msg_prefix="", html=False
    ):
        # convenience method to check the status separately, which yields nicer error messages
        self.assertStatus(response, status_code)
        # same for the substring check
        self.assertIn(
            text,
            response.content.decode(response.charset),
            f"Could not find {text} in the following response:\n{response.content.decode(response.charset)}",
        )
        return super().assertContains(
            response, text, count, status_code, msg_prefix, html
        )

    def assertAllSupportedRRSetTypes(self, types):
        self.assertEqual(
            types,
            self.SUPPORTED_RR_SET_TYPES,
            "Either some RR types given are unsupported, or not all "
            "supported RR types were in the given set.",
        )

    def assertEmailSent(
        self,
        subject_contains="",
        body_contains=None,
        recipient=None,
        reset=True,
        pattern=None,
    ):
        total = 1
        self.assertEqual(
            len(mail.outbox),
            total,
            "Expected %i message in the outbox, but found %i."
            % (total, len(mail.outbox)),
        )
        email = mail.outbox[-1]
        self.assertTrue(
            subject_contains in email.subject,
            "Expected '%s' in the email subject, but found '%s'"
            % (subject_contains, email.subject),
        )
        if type(body_contains) != list:
            body_contains = [] if body_contains is None else [body_contains]
        for elem in body_contains:
            self.assertTrue(
                elem in email.body,
                f"Expected '{elem}' in the email body, but found '{email.body}'",
            )
        if recipient is not None:
            if isinstance(recipient, list):
                self.assertListEqual(recipient, email.recipients())
            else:
                self.assertIn(recipient, email.recipients())
        body = email.body
        self.assertIn("user_id = ", body)
        if reset:
            mail.outbox = []
        return body if not pattern else re.search(pattern, body).group(1)

    def assertConfirmationLinkRedirect(self, confirmation_link):
        response = self.client.get(confirmation_link)
        self.assertResponse(response, status.HTTP_406_NOT_ACCEPTABLE)
        response = self.client.get(confirmation_link, HTTP_ACCEPT="text/html")
        self.assertResponse(response, status.HTTP_302_FOUND)
        self.assertNoEmailSent()

    def assertNoEmailSent(self):
        self.assertFalse(
            mail.outbox,
            "Expected no email to be sent, but %i were sent. First subject line is '%s'."
            % (len(mail.outbox), mail.outbox[0].subject if mail.outbox else "<n/a>"),
        )


class PublicSuffixMockMixin:
    def _mock_get_public_suffix(self, domain_name, public_suffixes=None):
        if public_suffixes is None:
            public_suffixes = settings.LOCAL_PUBLIC_SUFFIXES | self.PUBLIC_SUFFIXES
        # Poor man's PSL interpreter. First, find all known suffixes covering the domain.
        suffixes = [
            suffix
            for suffix in public_suffixes
            if ".{}".format(domain_name).endswith(".{}".format(suffix))
        ]
        # Also, consider TLD.
        suffixes += [domain_name.rsplit(".")[-1]]
        # Select the candidate with the most labels.
        return max(suffixes, key=lambda suffix: suffix.count("."))

    @staticmethod
    def _mock_is_public_suffix(name):
        return name == psl.get_public_suffix(name)

    def get_psl_context_manager(self, side_effect_parameter):
        if side_effect_parameter is None:
            return nullcontext()

        if callable(side_effect_parameter):
            side_effect = side_effect_parameter
        else:
            side_effect = partial(
                self._mock_get_public_suffix,
                public_suffixes=(
                    [side_effect_parameter]
                    if not isinstance(side_effect_parameter, list)
                    else list(side_effect_parameter)
                ),
            )

        return mock.patch.object(psl, "get_public_suffix", side_effect=side_effect)

    def setUpMockPatch(self):
        mock.patch.object(
            psl, "get_public_suffix", side_effect=self._mock_get_public_suffix
        ).start()
        mock.patch.object(
            psl, "is_public_suffix", side_effect=self._mock_is_public_suffix
        ).start()
        self.addCleanup(mock.patch.stopall)


class DomainOwnerTestCase(DesecTestCase, PublicSuffixMockMixin):
    """
    This test case creates a domain owner, some domains for her and some domains that are owned by other users.
    DomainOwnerTestCase.client is authenticated with the owner's token.
    """

    DYN = False
    NUM_OWNED_DOMAINS = 2
    NUM_OTHER_DOMAINS = 20

    owner = None
    my_domains = None
    other_domains = None
    my_domain = None
    other_domain = None
    token = None

    def setUpPdns(self):
        self.owner = self.create_user()

        domain_kwargs = {"suffix": self.AUTO_DELEGATION_DOMAINS if self.DYN else None}
        if self.DYN:
            domain_kwargs["minimum_ttl"] = 60
        self.my_domains = [
            self.create_domain(owner=self.owner, **domain_kwargs)
            for _ in range(self.NUM_OWNED_DOMAINS)
        ]
        self.other_domains = [
            self.create_domain(**domain_kwargs) for _ in range(self.NUM_OTHER_DOMAINS)
        ]

        if self.DYN:
            for domain in self.my_domains + self.other_domains:
                parent_domain = Domain.objects.get(name=domain.parent_domain_name)
                parent_domain.update_delegation(domain)

        self.my_domain = self.my_domains[0]
        self.other_domain = self.other_domains[0]

        self.create_rr_set(self.my_domain, ["127.0.0.1", "3.2.2.3"], type="A", ttl=123)
        self.create_rr_set(self.other_domain, ["40.1.1.1"], type="A", ttl=456)

        self.token = self.create_token(
            owner=self.owner, perm_create_domain=True, perm_delete_domain=True
        )

    def setUp(self):
        super().setUp()
        self.setUpPdns()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.plain)
        self.setUpMockPatch()


class DynDomainOwnerTestCase(DomainOwnerTestCase):
    DYN = True

    @classmethod
    def request_pdns_zone_axfr(cls, name=None):
        return super().request_pdns_zone_axfr(name.lower() if name else None)

    @classmethod
    def request_pdns_zone_update(cls, name=None):
        return super().request_pdns_zone_update(name.lower() if name else None)

    def _assertDynDNS12Update(self, requests, mock_remote_addr="", **kwargs):
        with self.assertRequests(requests):
            if mock_remote_addr:
                return self.client.get(
                    self.reverse("v1:dyndns12update"),
                    kwargs,
                    REMOTE_ADDR=mock_remote_addr,
                )
            else:
                return self.client.get(self.reverse("v1:dyndns12update"), kwargs)

    def assertDynDNS12Update(
        self, domain_name=None, mock_remote_addr="", expect_update=True, **kwargs
    ):
        if expect_update:
            pdns_name = (
                self._normalize_name(domain_name).lower() if domain_name else None
            )
            requests = [
                self.request_pdns_zone_update(name=pdns_name),
                self.request_pdns_zone_axfr(name=pdns_name),
            ]
        else:
            requests = []
        return self._assertDynDNS12Update(requests, mock_remote_addr, **kwargs)

    def assertDynDNS12NoUpdate(self, *args, **kwargs):
        return self.assertDynDNS12Update(expect_update=False, *args, **kwargs)

    def setUp(self):
        super().setUp()
        self.client_token_authorized = self.client_class()
        self.client.set_credentials_basic_auth(
            self.my_domain.name.lower(), self.token.plain
        )
        self.client_token_authorized.set_credentials_token_auth(self.token.plain)


class AuthenticatedRRSetBaseTestCase(DomainOwnerTestCase):
    UNSUPPORTED_TYPES = RR_SET_TYPES_UNSUPPORTED
    AUTOMATIC_TYPES = RR_SET_TYPES_AUTOMATIC
    ALLOWED_TYPES = RR_SET_TYPES_MANAGEABLE

    SUBNAMES = [
        "foo",
        "bar.baz",
        "q.w.e.r.t",
        "*",
        "*.foobar",
        "_",
        "-foo.test",
        "_bar",
    ]

    @classmethod
    def _test_rr_sets(cls, subname=None, type_=None, records=None, ttl=None):
        """
        Gives a list of example RR sets for testing.
        Args:
            subname: Filter by subname. None to allow any.
            type_: Filter by type. None to allow any.
            records: Filter by records. Must match exactly. None to allow any.
            ttl: Filter by ttl. None to allow any.

        Returns: Returns a list of tuples that represents example RR sets represented as 4-tuples consisting of
        subname, type_, records, ttl
        """
        # TODO add more examples of cls.ALLOWED_TYPES
        # NOTE The validity of the RRset contents it *not* verified. We currently leave this task to pdns.
        rr_sets = (
            [
                ("", "A", ["1.2.3.4"], 3620),
                ("test", "A", ["2.2.3.4"], 3620),
                ("test", "TXT", ['"foobar"'], 3620),
            ]
            + [
                (subname_, "TXT", ['"hey ho, let\'s go!"'], 134)
                for subname_ in cls.SUBNAMES
            ]
            + [
                (subname_, type_, ["10 mx1.example.com."], 101)
                for subname_ in cls.SUBNAMES
                for type_ in ["MX", "SPF"]
            ]
            + [(subname_, "A", ["1.2.3.4"], 187) for subname_ in cls.SUBNAMES]
        )

        if subname or type_ or records or ttl:
            rr_sets = [
                rr_set
                for rr_set in rr_sets
                if (
                    (subname is None or subname == rr_set[0])
                    and (type_ is None or type_ == rr_set[1])
                    and (records is None or records == rr_set[2])
                    and (ttl is None or ttl == rr_set[3])
                )
            ]
        return rr_sets

    def setUp(self):
        super().setUp()
        suffix = self.AUTO_DELEGATION_DOMAINS if self.DYN else None
        self.my_empty_domain = self.create_domain(owner=self.owner, suffix=suffix)
        self.my_rr_set_domain = self.create_domain(owner=self.owner, suffix=suffix)
        self.other_rr_set_domain = self.create_domain(suffix="")
        for domain in [self.my_rr_set_domain, self.other_rr_set_domain]:
            for subname, type_, records, ttl in self._test_rr_sets():
                self.create_rr_set(
                    domain, subname=subname, type=type_, records=records, ttl=ttl
                )
