from conftest import DeSECAPIV1Client


def test_homepage(api_anon: DeSECAPIV1Client):
    assert api_anon.get("/").json() == {
        "register": f"{api_anon.base_url}/auth/",
        "login": f"{api_anon.base_url}/auth/login/",
        "reset-password": f"{api_anon.base_url}/auth/account/reset-password/",
    }
