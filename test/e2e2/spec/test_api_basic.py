import os

from conftest import DeSECAPIV1Client


def test_homepage(api_anon: DeSECAPIV1Client):
    assert api_anon.get("/").json() == {
        "register": f"{api_anon.base_url}/auth/",
        "login": f"{api_anon.base_url}/auth/login/",
        "reset-password": f"{api_anon.base_url}/auth/account/reset-password/",
    }


def test_get_desec_io(api_anon: DeSECAPIV1Client):
    response = api_anon.get("https://get.desec." + os.environ['DESECSTACK_DOMAIN'], allow_redirects=False)
    assert 300 < response.status_code < 400
    assert response.headers['Location'] == f"https://desec.{os.environ['DESECSTACK_DOMAIN']}/"
