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

    # Verify that email address local part is stored as provided, and hostname is lowercased
    email_name, domain_part = api_user.email.strip().rsplit('@', 1)
    assert user["email"] == email_name + '@' + domain_part.lower()
    assert api_user.headers['Authorization'].startswith('Token ')
    assert len(api_user.headers['Authorization']) > len('Token ') + 10


def test_register_login_email_case_variation(api_user: DeSECAPIV1Client, api_anon: DeSECAPIV1Client):
    # Invert email casing
    email2 = ''.join(l.lower() if l.isupper() else l.upper() for l in api_user.email)
    password2 = "foobar13"

    # Try registering an account (should always return success, even if address with any casing is taken)
    assert api_anon.register(email2, password2)[1].json() == {"detail": "Welcome!"}

    # Verify that login is possible regardless of email spelling, but only with the first user's password
    assert api_anon.login(email2, password2).status_code == 403
    assert "token" in api_anon.login(email2, api_user.password).json()
