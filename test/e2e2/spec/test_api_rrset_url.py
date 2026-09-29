import pytest

from conftest import DeSECAPIV1Client


# The subname part of an RRset URL can be written plainly, or terminated with
# `...`. The zone apex has no plain form, because `rrsets//{type}/` does not
# survive URL normalization, and is written as `@` or as `...`.
#
# The exhaustive matrix over subnames lives in the API test suite; what needs
# the full stack is that these unusual characters survive the HTTP layer in
# front of the API, and that a write made through such a URL reaches the DNS.

TTL = 3600


@pytest.mark.parametrize("subname", ['', 'www'])
def test_url_forms_address_the_same_rrset(api_user_domain: DeSECAPIV1Client, subname: str):
    api = api_user_domain
    assert api.rr_set_create(api.domain, 'A', ['1.2.3.4'], subname=subname, ttl=TTL).status_code == 201

    urls = [f"/domains/{api.domain}/rrsets/{subname}.../A/"]
    urls.append(
        f"/domains/{api.domain}/rrsets/@/A/" if not subname
        else f"/domains/{api.domain}/rrsets/{subname}/A/"
    )

    responses = [api.get(url) for url in urls]
    for response in responses:
        assert response.status_code == 200
        assert response.json()['subname'] == subname
        assert response.json()['records'] == ['1.2.3.4']
    assert responses[0].json() == responses[1].json()


def test_apex_not_addressable_with_empty_subname(api_user_domain: DeSECAPIV1Client):
    # This is the reason the '@' and '...' forms exist: the double slash does
    # not survive URL normalization, so the apex cannot be addressed by leaving
    # the subname empty.
    api = api_user_domain
    assert api.rr_set_create(api.domain, 'A', ['1.2.3.4'], ttl=TTL).status_code == 201

    assert api.get(f"/domains/{api.domain}/rrsets//A/").status_code == 404
    assert api.get(f"/domains/{api.domain}/rrsets/.../A/").status_code == 200


def test_apex_dns(api_user_domain: DeSECAPIV1Client):
    # Writes through the '...' URL take effect in the DNS, not just in the API.
    api = api_user_domain
    url = f"/domains/{api.domain}/rrsets/.../A/"

    assert api.rr_set_create(api.domain, 'A', ['1.2.3.4'], ttl=TTL).status_code == 201
    api.assert_rrsets({('', 'A'): (TTL, {'1.2.3.4'})})

    assert api.patch(url, data={'records': ['5.6.7.8']}).status_code == 200
    api.assert_rrsets({('', 'A'): (TTL, {'5.6.7.8'})})

    assert api.delete(url).status_code == 204
    api.assert_rrsets({('', 'A'): (TTL, {})})
