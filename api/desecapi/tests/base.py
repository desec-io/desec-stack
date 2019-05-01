import base64
import random
import re
import string

from django.utils import timezone
from httpretty import httpretty, core as hr_core
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework.utils import json

from api import settings
from desecapi.models import User, Domain, Token, RRset, RR


class DesecAPIClient(APIClient):

    @staticmethod
    def _http_header_base64_conversion(content):
        return base64.b64encode(content.encode()).decode()

    def set_credentials(self, authorization):
        self.credentials(HTTP_AUTHORIZATION=authorization)

    def set_credentials_basic_auth(self, part_1, part_2=None):
        if not part_1 and not part_2:
            self.set_credentials('')
        else:
            s = part_1 if not part_2 else '%s:%s' % (part_1, part_2)
            self.set_credentials('Basic ' + self._http_header_base64_conversion(s))

    def set_credentials_token_auth(self, token):
        if token is None:
            self.set_credentials('')
        else:
            self.set_credentials('Token ' + token)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reverse = DesecTestCase.reverse

    def post_rr_set(self, domain_name, **kwargs):
        kwargs.setdefault('subname', '')
        kwargs.setdefault('ttl', 60)
        return self.post(
            self.reverse('v1:rrsets', name=domain_name),
            kwargs,
        )

    def get_rr_sets(self, domain_name, **kwargs):
        return self.get(
            self.reverse('v1:rrsets', name=domain_name),
            kwargs
        )

    def get_rr_set(self, domain_name, subname, type_):
        return self.get(
            self.reverse('v1:rrset@', name=domain_name, subname=subname, type=type_)
        )

    def put_rr_set(self, domain_name, subname, type_, **kwargs):
        return self.put(
            self.reverse('v1:rrset@', name=domain_name, subname=subname, type=type_),
            kwargs
        )

    def patch_rr_set(self, domain_name, subname, type_, **kwargs):
        return self.patch(
            self.reverse('v1:rrset@', name=domain_name, subname=subname, type=type_),
            kwargs
        )

    def delete_rr_set(self, domain_name, subname, type_):
        return self.delete(
            self.reverse('v1:rrset@', name=domain_name, subname=subname, type=type_)
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

    def __init__(self, test_case, expected_requests, single_expectation_single_request=True, expect_order=True):
        """
        Initialize a context that checks for made HTTP requests.

        Args:
            test_case: Test case in which this context lives. Used to fail test if observed requests do not meet
            expectations.
            expected_requests: (Possibly nested) list of requests, represented by kwarg-dictionaries for
            `httpretty.register_uri`.
            single_expectation_single_request: If True (default), each expected request needs to be matched by exactly
            one observed request.
            expect_order: If True (default), requests made are expected in order of expectations given.
        """
        self.test_case = test_case
        self.expected_requests = list(self._flatten_nested_lists(expected_requests))
        self.single_expectation_single_request = single_expectation_single_request
        self.expect_order = expect_order
        self.old_httpretty_entries = None

    def __enter__(self):
        hr_core.POTENTIAL_HTTP_PORTS.add(8081)  # FIXME should depend on self.expected_requests
        self.expected_requests = self.expected_requests
        self.old_httpretty_entries = httpretty._entries.copy()  # FIXME accessing private properties of httpretty
        for request in self.expected_requests:
            httpretty.register_uri(**request)

    @staticmethod
    def _find_matching_request(pattern, requests):
        for request in requests:
            if pattern['method'] == request[0] and pattern['uri'].match(request[1]):
                return request
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        # organize seen requests in a primitive data structure
        seen_requests = [
            (r.command, 'http://%s%s' % (r.headers['Host'], r.path)) for r in httpretty.latest_requests
        ]
        httpretty.reset()
        hr_core.POTENTIAL_HTTP_PORTS.add(8081)  # FIXME should depend on self.expected_requests
        httpretty._entries = self.old_httpretty_entries
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
                        'Checking of multiple (possibly zero) requests per expectation and checking of request '
                        'order simultaneously is not implemented, sorry.')
                if unmatched_requests:
                    match = self._find_matching_request(request, [unmatched_requests[0]])
            else:
                match = self._find_matching_request(
                    request, unmatched_requests if self.single_expectation_single_request else seen_requests)

            # check match
            if not match and self.single_expectation_single_request:
                self.test_case.fail(('Expected to see a %s request on\n\n%s,\n\nbut only saw these %i '
                                     'requests:\n\n%s\n\nAll expected requests:\n\n%s\n\n'
                                     'Hint: check for possible duplicates in your expectation.\n' +
                                     ('Hint: Is the expectation order correct?' if self.expect_order else '')) % (
                                        request['method'], request['uri'], len(seen_requests),
                                        '\n'.join(map(str, seen_requests)),
                                        '\n'.join(map(str, [(r['method'], r['uri']) for r in self.expected_requests])),
                                     ))
            if match:
                unmatched_requests.remove(match)

        # see if any requests were unexpected
        if unmatched_requests and self.single_expectation_single_request:
            self.test_case.fail('While waiting for %i request(s), we saw %i unexpected request(s). The unexpected '
                                'request(s) was/were:\n\n%s\n\nAll recorded requests:\n\n%s\n\nAll expected requests:'
                                '\n\n%s' % (
                                    len(self.expected_requests),
                                    len(unmatched_requests),
                                    '\n'.join(map(str, unmatched_requests)),
                                    '\n'.join(map(str, seen_requests)),
                                    '\n'.join(map(str, [(r['method'], r['uri']) for r in self.expected_requests])),
                                ))


class MockPDNSTestCase(APITestCase):
    """
    This test case provides a "mocked Internet" environment with a mock pdns API interface. All internet connections,
    HTTP or otherwise, that this test case is unaware of will result in an exception.

    By default, requests are intercepted but unexpected will result in a failed test. To set pdns API request
    expectations, use the `with MockPDNSTestCase.assertPdns*` context managers.

    Subclasses may not touch httpretty.enable() or httpretty.disable(). For 'local' usage, httpretty.register_uri()
    and httpretty.reset() may be used.
    """

    PDNS_ZONES = r'/zones'
    PDNS_ZONE_CRYPTO_KEYS = r'/zones/(?P<id>[^/]+)/cryptokeys'
    PDNS_ZONE = r'/zones/(?P<id>[^/]+)'
    PDNS_ZONE_NOTIFY = r'/zones/(?P<id>[^/]+)/notify'

    @classmethod
    def get_full_pdns_url(cls, path_regex, ns='LORD', **kwargs):
        api = getattr(settings, 'NS%s_PDNS_API' % ns)
        return re.compile('^' + api + cls.fill_regex_groups(path_regex, **kwargs) + '$')

    @classmethod
    def fill_regex_groups(cls, template, **kwargs):
        s = template
        for name, value in kwargs.items():
            if value is None:
                continue
            pattern = r'\(\?P\<%s\>[^\)]+\)' % name
            if not re.search(pattern, s):
                raise ValueError('Tried to fill field %s in template %s, but it does not exist.' % (name, template))
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

        return name.translate(str.maketrans({'/': '=2F', '_': '=5F'}))  # make sure =5F is not lower-cased

    @classmethod
    def _normalize_name(cls, arg):
        if not arg:
            return None

        if not isinstance(arg, list):
            return cls._normalize_name([arg])[0]
        else:
            return [x.rstrip('.') + '.' for x in arg]

    @classmethod
    def request_pdns_zone_create(cls):
        return {
            'method': 'POST',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONES),
            'status': 201,
            'body': None,
        }

    @classmethod
    def request_pdns_zone_create_422(cls):
        request = cls.request_pdns_zone_create()
        request['status'] = 422
        return request

    @classmethod
    def request_pdns_zone_create_already_exists(cls, existing_domains=None):
        existing_domains = cls._normalize_name(existing_domains)

        def request_callback(r, _, response_headers):
            body = json.loads(r.parsed_body)
            if not existing_domains or body['name'] in existing_domains:
                return [422, response_headers, json.dumps({'error': 'Domain \'%s\' already exists' % body['name']})]
            else:
                return [200, response_headers, '']

        request = cls.request_pdns_zone_create_422()
        request['body'] = request_callback
        request.pop('status')
        return request

    @classmethod
    def request_pdns_zone_delete(cls, name=None, ns='LORD'):
        return {
            'method': 'DELETE',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONE, ns=ns, id=cls._pdns_zone_id_heuristic(name)),
            'status': 200,
            'body': None,
        }

    @classmethod
    def request_pdns_zone_update(cls, name=None):
        return {
            'method': 'PATCH',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONE, id=cls._pdns_zone_id_heuristic(name)),
            'status': 200,
            'body': None,
        }

    @classmethod
    def request_pdns_zone_update_unknown_type(cls, name=None, unknown_types=None):
        def request_callback(r, _, response_headers):
            body = json.loads(r.parsed_body)
            if not unknown_types or body['rrsets'][0]['type'] in unknown_types:
                return [
                    422, response_headers,
                    json.dumps({'error': 'Mocked error. Unknown RR type %s.' % body['rrsets'][0]['type']})
                ]
            else:
                return [200, response_headers, None]

        request = cls.request_pdns_zone_update(name)
        request['body'] = request_callback
        request.pop('status')
        return request

    @classmethod
    def request_pdns_zone_retrieve(cls, name=None):
        return {
            'method': 'GET',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONE, id=cls._pdns_zone_id_heuristic(name)),
            'status': 200,
            'body': json.dumps({
                'rrsets': [{
                    'comments': [],
                    'name': cls._normalize_name(name) if name else 'test.mock.',
                    'ttl': 60,
                    'type': 'NS',
                    'records': [{'content': ns} for ns in settings.DEFAULT_NS],
                }]
            }),
        }

    @classmethod
    def request_pdns_zone_retrieve_crypto_keys(cls, name=None):
        return {
            'method': 'GET',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONE_CRYPTO_KEYS, id=cls._pdns_zone_id_heuristic(name)),
            'status': 200,
            'body': json.dumps([
                {
                    'active': True,
                    'algorithm': 'ECDSAP256SHA256',
                    'bits': 256,
                    'dnskey': '257 3 13 EVBcsqrnOp6RGWtsrr9QW8cUtt/'
                              'WI5C81RcCZDTGNI9elAiMQlxRdnic+7V+b7jJDE2vgY08qAbxiNh5NdzkzA==',
                    'ds': [
                        '62745 13 1 642d70d9bb84903ca4c4ca08a6e4f1e9465aeaa6',
                        '62745 13 2 5cddaeaa383e2ea7de49bd1212bf520228f0e3b334626517e5f6a68eb85b48f6',
                        '62745 13 4 b3f2565901ddcb0b78337301cf863d1045774377bca05c7ad69e17a167734b92'
                        '9f0a49b7edcca913eb6f5dfeac4645b8'
                    ],
                    'flags': 257,
                    'id': 179425943,
                    'keytype': key_type,
                    'type': 'Cryptokey',
                }
                for key_type in ['csk', 'ksk', 'zsk']
            ])
        }

    @classmethod
    def request_pdns_zone_notify(cls, name=None):
        return {
            'method': 'PUT',
            'uri': cls.get_full_pdns_url(cls.PDNS_ZONE_NOTIFY, id=cls._pdns_zone_id_heuristic(name)),
            'status': 200,
            'body': None,
        }

    def assertPdnsRequests(self, *expected_requests, expect_order=True):
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

    def assertPdnsNoRequestsBut(self, *expected_requests):
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

    def assertPdnsZoneCreation(self):
        """
        Asserts that nslord is contact and a zone is created.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=[
                self.request_pdns_zone_create()
            ],
        )

    def assertPdnsZoneDeletion(self, name=None):
        """
        Asserts that nslord and nsmaster are contacted to delete a zone.
        Args:
            name: If given, the test is restricted to the name of this zone.
        """
        return AssertRequestsContextManager(
            test_case=self,
            expected_requests=[
                self.request_pdns_zone_delete(ns='LORD', name=name),
                self.request_pdns_zone_delete(ns='MASTER', name=name),
            ],
        )

    def assertStatus(self, response, status):
        if response.status_code != status:
            self.fail((
                'Expected a response with status %i, but saw response with status %i. ' +
                (
                    '\n@@@@@ THE REQUEST CAUSING THIS RESPONSE WAS UNEXPECTED BY THE TEST @@@@@\n'
                    if response.status_code == 599 else ''
                ) +
                'The response was %s.\n'
                'The response body was\n\n%s') % (
                      status,
                      response.status_code,
                      response,
                      str(response.data).replace('\\n', '\n'),
                ))

    @classmethod
    def setUpTestData(cls):
        httpretty.enable(allow_net_connect=False)
        httpretty.reset()
        hr_core.POTENTIAL_HTTP_PORTS.add(8081)  # FIXME static dependency on settings variable
        for request in [
            cls.request_pdns_zone_create(),
            cls.request_pdns_zone_notify(),
            cls.request_pdns_zone_update(),
            cls.request_pdns_zone_retrieve_crypto_keys(),
            cls.request_pdns_zone_retrieve()
        ]:
            httpretty.register_uri(**request)
        cls.setUpTestDataWithPdns()
        httpretty.reset()

    @classmethod
    def setUpTestDataWithPdns(cls):
        """
        Override this method to set up test data. During the run of this method, httpretty is configured to accept
        all pdns API requests.
        """
        pass

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        httpretty.disable()

    def setUp(self):
        def request_callback(r, _, response_headers):
            return [
                599,
                response_headers,
                json.dumps(
                    {
                        'MockPDNSTestCase': 'This response was generated upon an unexpected request.',
                        'request': str(r),
                        'method': str(r.method),
                        'requestline': str(r.raw_requestline),
                        'host': str(r.headers['Host']) if 'Host' in r.headers else None,
                        'headers': {str(key): str(value) for key, value in r.headers.items()},
                    },
                    indent=4
                )
            ]

        super().setUp()
        httpretty.reset()
        hr_core.POTENTIAL_HTTP_PORTS.add(8081)  # FIXME should depend on self.expected_requests
        for method in [
            httpretty.GET, httpretty.PUT, httpretty.POST, httpretty.DELETE, httpretty.HEAD, httpretty.PATCH,
            httpretty.OPTIONS, httpretty.CONNECT
        ]:
            for ns in ['LORD', 'MASTER']:
                httpretty.register_uri(
                    method,
                    self.get_full_pdns_url('.*', ns),
                    body=request_callback,
                    status=599,
                    priority=-100,
                )


class DesecTestCase(MockPDNSTestCase):
    """
    This test case is run in the "standard" deSEC e.V. setting, i.e. with an API that is aware of the public suffix
    domains AUTO_DELEGATION_DOMAINS.

    The test case aims to be as close to the deployment as possible and may be extended as the deployment evolves.

    The test case provides an admin user and a regular user for testing.
    """
    client_class = DesecAPIClient

    AUTO_DELEGATION_DOMAINS = ['dedyn.io']  # TODO replace with project wide settings
    PUBLIC_SUFFIXES = ['de', 'com', 'io', 'gov.cd', 'edu.ec', 'xxx', 'pinb.gov.pl', 'valer.ostfold.no', 'kota.aichi.jp']

    @classmethod
    def reverse(cls, view_name, **kwargs):
        return reverse(view_name, kwargs=kwargs)

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()
        random.seed(0xde5ec)
        cls.admin = cls.create_user(is_admin=True)
        cls.add_domains = [cls.create_domain(name=name) for name in cls.AUTO_DELEGATION_DOMAINS]
        cls.user = cls.create_user()

    @classmethod
    def random_string(cls, length=6, chars=string.ascii_letters + string.digits):
        return ''.join(random.choice(chars) for _ in range(length))

    @classmethod
    def random_password(cls, length=12):
        return cls.random_string(
            length,
            chars=string.ascii_letters + string.digits + string.punctuation +
            'some 💩🐬 UTF-8: “红色联合”对“四·二八兵团”总部大楼的攻击已持续了两天"'
        )

    @classmethod
    def random_ip(cls, proto=None):
        proto = proto or random.choice([4, 6])
        if proto == 4:
            return '.'.join([str(random.randrange(256)) for _ in range(4)])
        elif proto == 6:
            return '2001:' + ':'.join(['%x' % random.randrange(16**4) for _ in range(7)])
        else:
            raise ValueError('Unknown IP protocol version %s. Expected int 4 or int 6.' % str(proto))

    @classmethod
    def random_username(cls, host=None):
        host = host or cls.random_domain_name(suffix=random.choice(cls.PUBLIC_SUFFIXES))
        return cls.random_string() + '+test@' + host.lower()

    @classmethod
    def random_domain_name(cls, suffix=None):
        if not suffix:
            suffix = random.choice(cls.PUBLIC_SUFFIXES)
        return (random.choice(string.ascii_letters) + cls.random_string() + '--test' + '.' + suffix).lower()

    @classmethod
    def create_token(cls, user):
        token = Token.objects.create(user=user)
        token.save()
        return token

    @classmethod
    def create_user(cls, **kwargs):
        kwargs.setdefault('email', cls.random_username())
        user = User(**kwargs)
        user.plain_password = cls.random_string(length=12)
        user.set_password(user.plain_password)
        user.save()
        return user

    @classmethod
    def create_domain(cls, suffix=None, **kwargs):
        kwargs.setdefault('owner', cls.create_user())
        kwargs.setdefault('name', cls.random_domain_name(suffix=suffix))
        domain = Domain(**kwargs)
        domain.save()
        return domain

    @classmethod
    def create_rr_set(cls, domain, records, **kwargs):
        if isinstance(domain, str):
            domain = Domain.objects.get_or_create(name=domain)
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
        parents = [parent for parent in cls.AUTO_DELEGATION_DOMAINS if name.endswith('.' + parent)]
        if not parents:
            raise ValueError('Could not find auto delegation zone for zone %s; searched in %s' % (
                name,
                cls.AUTO_DELEGATION_DOMAINS
            ))
        return parents[0]

    @classmethod
    def requests_desec_domain_creation(cls, name=None):
        return [
            cls.request_pdns_zone_create(),
            cls.request_pdns_zone_notify(name=name),
            cls.request_pdns_zone_retrieve(name=name),
            cls.request_pdns_zone_retrieve_crypto_keys(name=name),
        ]

    @classmethod
    def requests_desec_domain_deletion(cls, name=None):
        return [
            cls.request_pdns_zone_delete(name=name, ns='LORD'),
            cls.request_pdns_zone_delete(name=name, ns='MASTER'),
        ]

    @classmethod
    def requests_desec_domain_creation_auto_delegation(cls, name=None):
        delegate_at = cls._find_auto_delegation_zone(name)
        return cls.requests_desec_domain_creation(name=name) + [
            cls.request_pdns_zone_update(name=delegate_at),
            cls.request_pdns_zone_notify(name=delegate_at),
            cls.request_pdns_zone_retrieve_crypto_keys(name=name),
        ]

    @classmethod
    def requests_desec_domain_deletion_auto_delegation(cls, name=None):
        delegate_at = cls._find_auto_delegation_zone(name)
        return [
            cls.request_pdns_zone_update(name=delegate_at),
            cls.request_pdns_zone_notify(name=delegate_at),
            cls.request_pdns_zone_delete(name=name, ns='LORD'),
            cls.request_pdns_zone_delete(name=name, ns='MASTER'),
        ]

    @classmethod
    def requests_desec_rr_sets_update(cls, name=None):
        return [
            cls.request_pdns_zone_update(name=name),
            cls.request_pdns_zone_notify(name=name),
        ]


class DomainOwnerTestCase(DesecTestCase):
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

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()

        cls.owner = cls.create_user(dyn=cls.DYN)

        cls.my_domains = [
            cls.create_domain(suffix=random.choice(cls.AUTO_DELEGATION_DOMAINS) if cls.DYN else '', owner=cls.owner)
            for _ in range(cls.NUM_OWNED_DOMAINS)
        ]
        cls.other_domains = [
            cls.create_domain(suffix=random.choice(cls.AUTO_DELEGATION_DOMAINS) if cls.DYN else '')
            for _ in range(cls.NUM_OTHER_DOMAINS)
        ]

        cls.my_domain = cls.my_domains[0]
        cls.other_domain = cls.other_domains[0]

        cls.create_rr_set(cls.my_domain, ['127.0.0.1', '127.0.1.1'], type='A', ttl=123)
        cls.create_rr_set(cls.other_domain, ['40.1.1.1', '40.2.2.2'], type='A', ttl=456)

        cls.token = cls.create_token(user=cls.owner)

    def setUp(self):
        super().setUp()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)


class LockedDomainOwnerTestCase(DomainOwnerTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner.locked = timezone.now()
        cls.owner.save()


class DynDomainOwnerTestCase(DomainOwnerTestCase):
    DYN = True

    @classmethod
    def request_pdns_zone_notify(cls, name=None):
        return super().request_pdns_zone_notify(name.lower() if name else None)

    @classmethod
    def request_pdns_zone_update(cls, name=None):
        return super().request_pdns_zone_update(name.lower() if name else None)

    def _assertDynDNS12Update(self, requests, mock_remote_addr='', **kwargs):
        with self.assertPdnsRequests(requests):
            if mock_remote_addr:
                return self.client.get(self.reverse('v1:dyndns12update'), kwargs, REMOTE_ADDR=mock_remote_addr)
            else:
                return self.client.get(self.reverse('v1:dyndns12update'), kwargs)

    def assertDynDNS12Update(self, domain_name=None, mock_remote_addr='', **kwargs):
        pdns_name = self._normalize_name(domain_name).lower() if domain_name else None
        return self._assertDynDNS12Update(
            [self.request_pdns_zone_update(name=pdns_name), self.request_pdns_zone_notify(name=pdns_name)],
            mock_remote_addr,
            **kwargs
        )

    def assertDynDNS12NoUpdate(self, mock_remote_addr='', **kwargs):
        return self._assertDynDNS12Update([], mock_remote_addr, **kwargs)

    def setUp(self):
        super().setUp()
        self.client_token_authorized = self.client_class()
        self.client.set_credentials_basic_auth(self.my_domain.name, self.token.key)
        self.client_token_authorized.set_credentials_token_auth(self.token.key)
