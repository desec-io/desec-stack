from conftest import DeSECAPIV1Client


def test_register(api_anon: DeSECAPIV1Client):
    email = "e2e2@desec.test"
    password = "foobar12"

    assert api_anon.register(email, password)[1].json() == {"detail": "Welcome!"}
    assert "token" in api_anon.login(email, password).json()
    api = api_anon

    assert api.get("/").json() == {
        "domains": f"{api.base_url}/domains/",
        "tokens": f"{api.base_url}/auth/tokens/",
        "logout": f"{api.base_url}/auth/logout/",
        "account": {
            "change-email": f"{api.base_url}/auth/account/change-email/",
            "delete": f"{api.base_url}/auth/account/delete/",
            "reset-password": f"{api.base_url}/auth/account/reset-password/",
            "show": f"{api.base_url}/auth/account/",
        },
    }


def test_register2(api_user: DeSECAPIV1Client):
    user = api_user.get("/auth/account/").json()
    assert user["email"] == api_user.email
    assert api_user.headers['Authorization'].startswith('Token ')
    assert len(api_user.headers['Authorization']) > len('Token ') + 10
