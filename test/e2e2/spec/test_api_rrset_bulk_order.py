import pytest

from conftest import DeSECAPIV1Client


# The outcome of a bulk request must not depend on the order in which the RRsets
# are given. This does not come for free: pdns refuses to add a CNAME while a
# conflicting RRset is still present, so the API applies deletions before
# additions regardless of their position in the payload (desec-stack#220,
# PowerDNS/pdns#7501). The unit tests cover this against a mocked pdns and for
# one payload order only; these tests exercise both orders against the real
# thing (desec-stack#226).

TTL = 3600

CNAME_RECORDS = ['elk.example.net.']
AAAA_RECORDS = ['::1']


def replacement_payload(subname: str, remove_type: str, add_type: str, add_records: list) -> list:
    """Delete one RRset and create a conflicting one at the same subname, deletion first."""
    return [
        {'subname': subname, 'type': remove_type, 'ttl': TTL, 'records': []},
        {'subname': subname, 'type': add_type, 'ttl': TTL, 'records': add_records},
    ]


@pytest.mark.parametrize("method", ['patch', 'put'])
@pytest.mark.parametrize("deletion_first", [True, False])
@pytest.mark.parametrize("init_rrsets", [{('kibana', 'AAAA'): (TTL, set(AAAA_RECORDS))}])
def test_replace_rrset_with_cname(api_user_domain_rrsets: DeSECAPIV1Client, method: str, deletion_first: bool):
    api = api_user_domain_rrsets
    payload = replacement_payload('kibana', 'AAAA', 'CNAME', CNAME_RECORDS)
    if not deletion_first:
        payload.reverse()

    response = getattr(api, method)(f"/domains/{api.domain}/rrsets/", data=payload)
    assert response.status_code == 200
    api.assert_rrsets({
        ('kibana', 'AAAA'): (TTL, set()),
        ('kibana', 'CNAME'): (TTL, set(CNAME_RECORDS)),
    })


@pytest.mark.parametrize("method", ['patch', 'put'])
@pytest.mark.parametrize("deletion_first", [True, False])
@pytest.mark.parametrize("init_rrsets", [{('kibana', 'CNAME'): (TTL, set(CNAME_RECORDS))}])
def test_replace_cname_with_rrset(api_user_domain_rrsets: DeSECAPIV1Client, method: str, deletion_first: bool):
    api = api_user_domain_rrsets
    payload = replacement_payload('kibana', 'CNAME', 'AAAA', AAAA_RECORDS)
    if not deletion_first:
        payload.reverse()

    response = getattr(api, method)(f"/domains/{api.domain}/rrsets/", data=payload)
    assert response.status_code == 200
    api.assert_rrsets({
        ('kibana', 'CNAME'): (TTL, set()),
        ('kibana', 'AAAA'): (TTL, set(AAAA_RECORDS)),
    })
