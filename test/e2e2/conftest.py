import json
import os
import random
import re
import string
from json import JSONDecodeError
from typing import Optional, Tuple, Iterable, Callable

import dns
import dns.name
import dns.query
import pytest
import requests
from requests.exceptions import SSLError


@pytest.fixture()
def random_email() -> Callable[[], str]:
    return lambda: (
        "".join(random.choice(string.ascii_letters) for _ in range(10))
        + "@desec.test"
    )


@pytest.fixture()
def random_password() -> Callable[[], str]:
    return lambda: "".join(random.choice(string.ascii_letters) for _ in range(16))


@pytest.fixture()
def random_domainname() -> Callable[[], str]:
    return lambda: (
        "".join(random.choice(string.ascii_lowercase) for _ in range(16))
        + ".test"
    )


@pytest.fixture()
def random_local_public_suffix_domainname() -> Callable[[], str]:
    return lambda: (
        "".join(random.choice(string.ascii_lowercase) for _ in range(16))
        + ".dedyn."
        + os.environ['DESECSTACK_DOMAIN']
    )


class DeSECAPIV1Client:
    base_url = "https://desec." + os.environ["DESECSTACK_DOMAIN"] + "/api/v1"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "e2e2",
    }

    def __init__(self) -> None:
        super().__init__()
        self.email = None
        self.password = None
        self.domains = []

        # We support two certificate verification methods
        # (1) against self-signed certificates, if /autocert path is present
        # (this is usually the case when run inside a docker container)
        # (2) against the default certificate store, if /autocert is not available
        # (this is usually the case when run outside a docker container)
        self.verify = True
        self.verify_alt = [
            f'/autocert/desec.{os.environ["DESECSTACK_DOMAIN"]}.cer',
            f'/autocert/get.desec.{os.environ["DESECSTACK_DOMAIN"]}.cer',
        ]

    @staticmethod
    def _filter_response_output(output: dict) -> dict:
        try:
            output['challenge'] = output['challenge'][:10] + '...'
        except (KeyError, TypeError):
            pass
        return output

    def _do_request(self, *args, **kwargs):
        verify_list = [self.verify] + self.verify_alt
        exc = None
        for verify in verify_list:
            try:
                reply = requests.request(*args, **kwargs, verify=verify)
            except SSLError as e:
                print(f'API <<< SSL could not verify against "{verify}"')
                exc = e
            else:
                # note verification preference for next time
                self.verify = verify
                self.verify_alt = verify_list
                self.verify_alt.remove(self.verify)
                return reply
        print(f'API <<< SSL could not be verified against any verification method')
        raise exc

    def _request(self, method: str, *, path: str, data: Optional[dict] = None, **kwargs) -> requests.Response:
        if data is not None:
            data = json.dumps(data)

        url = self.base_url + path if re.match(r'^https?://', path) is None else path

        print(f"API >>> {method} {url}")
        if data:
            print(f"API >>> {type(data)}: {data}")

        response = self._do_request(
            method,
            url,
            data=data,
            headers=self.headers,
            **kwargs,
        )

        print(f"API <<< {response.status_code}")
        if response.text:
            try:
                print(f"API <<< {self._filter_response_output(response.json())}")
            except JSONDecodeError:
                print(f"API <<< {response.text}")

        return response

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path=path, **kwargs)

    def post(self, path: str, data: Optional[dict] = None, **kwargs) -> requests.Response:
        return self._request("POST", path=path, data=data, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._request("DELETE", path=path, **kwargs)

    def register(self, email: str, password: str) -> Tuple[requests.Response, requests.Response]:
        self.email = email
        self.password = password
        captcha = self.post("/captcha/")
        return captcha, self.post(
            "/auth/",
            data={
                "email": email,
                "password": password,
                "captcha": {
                    "id": captcha.json()["id"],
                    "solution": captcha.json()[
                        "content"
                    ],  # available via e2e configuration magic
                },
            },
        )

    def login(self, email: str, password: str) -> requests.Response:
        response = self.post(
            "/auth/login/", data={"email": email, "password": password}
        )
        token = response.json().get('token')
        if token is not None:
            self.headers["Authorization"] = f'Token {response.json()["token"]}'
        return response

    def domain_list(self) -> requests.Response:
        return self.get("/domains/")

    def domain_create(self, name) -> requests.Response:
        self.domains.append(name)
        return self.post(
            "/domains/",
            data={
                "name": name,
            }
        )

    def domain_destroy(self, name) -> requests.Response:
        self.domains.remove(name)
        return self.delete(f"/domains/{name}/")

    def rr_set_create(self, domain_name: str, rr_type: str, records: Iterable[str], subname: str = '',
                      ttl: int = 3600) -> requests.Response:
        return self.post(
            f"/domains/{domain_name}/rrsets/",
            data={
                "subname": subname,
                "type": rr_type,
                "ttl": ttl,
                "records": records,
            }
        )


@pytest.fixture
def api_anon() -> DeSECAPIV1Client:
    """
    Anonymous access to the API.
    """
    return DeSECAPIV1Client()


@pytest.fixture()
def api_user(random_email, random_password) -> DeSECAPIV1Client:
    """
    Access to the API with a fresh user account (zero domains, one token). Authorization header
    is preconfigured, email address and password are randomly chosen.
    """
    api = DeSECAPIV1Client()
    email = random_email()
    password = random_password()
    api.register(email, password)
    api.login(email, password)
    return api


@pytest.fixture()
def api_user_domain(api_user, random_domainname) -> DeSECAPIV1Client:
    """
    Access to the API with a fresh user account that owns a domain with random name. The domain has
    no records other than the default ones.
    """
    api_user.domain_create(random_domainname())
    return api_user


class NSClient:
    where = None

    def query(self, qname: str, qtype: str):
        print(f'DNS >>> {qname}/{qtype} @{self.where}')
        qname = dns.name.from_text(qname)
        qtype = dns.rdatatype.from_text(qtype)
        answer = dns.query.tcp(
            q=dns.message.make_query(qname, qtype),
            where=self.where,
            timeout=2
        )
        try:
            section = dns.message.AUTHORITY if qtype == dns.rdatatype.from_text('NS') else dns.message.ANSWER
            response = answer.find_rrset(section, qname, dns.rdataclass.IN, qtype)
            print(f'DNS <<< {response}')
            return {i.to_text() for i in response.items}
        except KeyError:
            print('DNS <<< !!! not found !!! Complete Answer below:\n' + answer.to_text())
            return {}


class NSLordClient(NSClient):
    where = os.environ["DESECSTACK_IPV4_REAR_PREFIX16"] + '.0.129'


@pytest.fixture()
def ns_lord() -> NSLordClient:
    return NSLordClient()
