import json
import os
import random
import string
from typing import Optional, Tuple

import pytest
import requests


class DeSECAPIV1Client:
    base_url = "https://desec." + os.environ["DESECSTACK_DOMAIN"] + "/api/v1"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "e2e2",
    }

    @staticmethod
    def random_email() -> str:
        return (
            "".join(random.choice(string.ascii_letters) for _ in range(10))
            + "@desec.test"
        )

    @staticmethod
    def random_password() -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(16))

    def __init__(self) -> None:
        super().__init__()
        self.email = None
        self.password = None

    def _request(self, method: str, *, path: str, data: Optional[dict] = None, **kwargs) -> requests.Response:
        if data is not None:
            data = json.dumps(data)

        return requests.request(
            method,
            self.base_url + path,
            data=data,
            headers=self.headers,
            verify=f'/autocert/desec.{os.environ["DESECSTACK_DOMAIN"]}.cer',
            **kwargs,
        )

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path=path, **kwargs)

    def post(self, path: str, data: Optional[dict] = None, **kwargs) -> requests.Response:
        return self._request("POST", path=path, data=data, **kwargs)

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
        token = self.post(
            "/auth/login/", data={"email": email, "password": password}
        )
        self.headers["Authorization"] = f'Token {token.json()["token"]}'
        return token


@pytest.fixture
def api_anon() -> DeSECAPIV1Client:
    """
    Anonymous access to the API.
    """
    return DeSECAPIV1Client()


@pytest.fixture()
def api_user(api_anon) -> DeSECAPIV1Client:
    """
    Access to the API with a fresh user account (zero domains, one token). Authorization header
    is preconfigured, email address and password are randomly chosen.
    """
    api = api_anon
    email = api.random_email()
    password = api.random_password()
    api.register(email, password)
    api.login(email, password)
    return api
