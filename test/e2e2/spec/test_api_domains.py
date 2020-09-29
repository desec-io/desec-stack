from conftest import DeSECAPIV1Client, random_domainname


def test_create(api_user: DeSECAPIV1Client):
    assert len(api_user.domain_list()) == 0
    assert api_user.domain_create(random_domainname()).status_code == 201
    assert len(api_user.domain_list()) == 1


def test_destroy(api_user_domain: DeSECAPIV1Client):
    n = len(api_user_domain.domain_list())
    assert api_user_domain.domain_destroy(api_user_domain.domain).status_code == 204
    assert len(api_user_domain.domain_list()) == n - 1
