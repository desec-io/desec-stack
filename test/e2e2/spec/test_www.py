import ipaddress
import os
import socket

import pytest
from requests import exceptions


https_url = "https://desec." + os.environ["DESECSTACK_DOMAIN"] + "/"
ipv4 = os.environ['DESECSTACK_IPV4_REAR_PREFIX16'] + '.0.128'
ipv6 = os.environ['DESECSTACK_IPV6_ADDRESS']

alt_svc = 'h3=":443"; ma=86400'
hsts_preload = 'max-age=31536000; includeSubDomains; preload'
hsts = {  # only the desec.* names are in the preload list
    'desec': hsts_preload,
    'www.desec': hsts_preload,
    'get.desec': hsts_preload,
    'dedyn': 'max-age=31536000',
    'www.dedyn': 'max-age=31536000',
    'checkip.dedyn': 'max-age=31536000',
    'checkipv4.dedyn': 'max-age=31536000',
    'checkipv6.dedyn': 'max-age=31536000',
    'update.dedyn': 'max-age=31536000',
    'update6.dedyn': 'max-age=31536000',
}


class HostsOverride:
    def __init__(self, host, ip):
        self.cache = {host: ip}

    def __enter__(self):
        self._getaddrinfo = socket.getaddrinfo
        socket.getaddrinfo = self.getaddrinfo

    def __exit__(self, type, value, traceback):
        socket.getaddrinfo = self._getaddrinfo

    def getaddrinfo(self, host, *args, **kwargs):
        try:
            host = self.cache[host]
        except KeyError:
            pass
        return self._getaddrinfo(host, *args, **kwargs)


@pytest.mark.parametrize("hostname", [
    f'{subname}.{os.environ["DESECSTACK_DOMAIN"]}' for subname in (
        'dedyn',
        'www.dedyn',
        'get.desec',
    )
])
@pytest.mark.parametrize("protocol", ['http', 'https'])
def test_redirects(api_anon, protocol, hostname):
    api_anon.headers = {}
    expected_locations = [https_url]
    if protocol == 'http':
        expected_locations.append(f'https://{hostname}/')
    if hostname.startswith('www.'):
        expected_locations.append('{}://{}/'.format(protocol, hostname.removeprefix('www.')))
    response = api_anon.get(f'{protocol}://{hostname}/', allow_redirects=False)
    assert response.headers['Location'] in expected_locations


@pytest.mark.parametrize("hostname", [
    f'{subname}.{os.environ["DESECSTACK_DOMAIN"]}' for subname in (
        'checkip.dedyn',
        'checkipv4.dedyn',
        'checkipv6.dedyn',
    )
])
@pytest.mark.parametrize("protocol", ['http', 'https'])
@pytest.mark.parametrize("server_ip", [ipv4, ipv6])
def test_checkip(api_anon, server_ip, protocol, hostname):
    api_anon.headers = {}
    ip_version = 'v6' if ':' in server_ip else 'v4'
    with HostsOverride(hostname, server_ip):
        if not hostname.startswith('checkip.') and not hostname.startswith(f'checkip{ip_version}.'):
            with pytest.raises(exceptions.ConnectionError) as excinfo:
                api_anon.get(f'{protocol}://{hostname}/', allow_redirects=False, verify=False)
            assert 'RemoteDisconnected' in str(excinfo)
            return

        response = api_anon.get(f'{protocol}://{hostname}/', allow_redirects=False)
        if protocol == 'http':
            assert response.headers['Location'] == f'https://{hostname}/'
        else:
            factories = {'v4': ipaddress.IPv4Address, 'v6': ipaddress.IPv6Address}
            assert factories[ip_version](response.text)


@pytest.mark.parametrize("hostname", [ipv4, f'[{ipv6}]'])
@pytest.mark.parametrize("protocol", ['http', 'https'])
def test_unknown_hosts(api_anon, protocol, hostname):
    api_anon.headers = {}
    with pytest.raises(exceptions.ConnectionError) as excinfo:
        api_anon.get(f'{protocol}://{hostname}/', allow_redirects=False, verify=False)
    assert 'RemoteDisconnected' in str(excinfo)


@pytest.mark.parametrize("url", [https_url + relpath for relpath in ('', 'signup')])
def test_security_headers(api_anon, url):
    api_anon.headers = {}
    # These come from the http (Alt-Svc), server (HSTS) and location (CSP) level, which only end
    # up in the same response because of add_header_inherit.
    # CSP hashes are for legacy browser support.
    # Source: https://github.com/vitejs/vite/tree/v5.0.10/packages/plugin-legacy#content-security-policy
    expected_headers = {
        'Strict-Transport-Security': hsts_preload,
        'Alt-Svc': alt_svc,
        'Content-Security-Policy': "default-src 'self'; frame-src 'none'; connect-src 'self'; font-src 'self' data:; "
                                   "img-src 'self' data:; media-src data:; "
                                   "script-src 'self' 'unsafe-eval' 'sha256-MS6/3FCg4WjP9gwgaBGwLpRCY6fZBgwmhVCdrPrNf3E=' 'sha256-tQjf8gvb2ROOMapIxFvFAYBeUJ0v1HCbOcSmDNXGtDo=' 'sha256-VA8O2hAdooB288EpSTrGLl7z3QikbWU9wwoebO/QaYk=' 'sha256-+5XkZFazzJo8n0iOP4ti/cLCMUudTf//Mzkb7xNPXIc='; "
                                   "style-src 'self' 'unsafe-inline'; base-uri 'self'; frame-ancestors 'none'; "
                                   "block-all-mixed-content; form-action 'none';",
        'X-Frame-Options': 'deny',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'X-XSS-Protection': '1; mode=block',
    }
    response = api_anon.get(url)
    for k, v in expected_headers.items():
        assert response.headers[k] == v


@pytest.mark.parametrize("subname,expected_hsts", hsts.items())
@pytest.mark.parametrize("protocol", ['http', 'https'])
def test_headers(api_anon, protocol, subname, expected_hsts):
    api_anon.headers = {}
    hostname = f'{subname}.{os.environ["DESECSTACK_DOMAIN"]}'
    headers = api_anon.get(f'{protocol}://{hostname}/', allow_redirects=False).headers
    # Strict-Transport-Security is for TLS connections only
    assert headers.get('Strict-Transport-Security') == (None if protocol == 'http' else expected_hsts)
    # Comparing for equality also catches a duplicate header, which requests joins by comma
    assert headers['Alt-Svc'] == alt_svc


@pytest.mark.parametrize("path", ['api/v1/', 'prometheus/'])
def test_headers_in_locations(api_anon, path):
    # Both locations are proxied, and /prometheus/ answers 401, so the headers are owed to `always`
    api_anon.headers = {}
    headers = api_anon.get(https_url + path, allow_redirects=False).headers
    assert headers['Strict-Transport-Security'] == hsts_preload
    assert headers['Alt-Svc'] == alt_svc


def test_compression(api_anon):
    # compression for supporting clients on static files
    assert api_anon.get(
        f'https://desec.{os.environ["DESECSTACK_DOMAIN"]}/',
        headers={'Accept-Encoding': 'Accept-Encoding: gzip, deflate'},
    ).headers['Content-Encoding'] == 'gzip'


def test_no_compression(api_anon):
    # no compression for non-supporting clients on static files
    assert 'Content-Encoding' not in api_anon.get(
        f'https://desec.{os.environ["DESECSTACK_DOMAIN"]}/',
    )
    # no compression for supporting clients on api
    assert 'Content-Encoding' not in api_anon.get(
        f'https://desec.{os.environ["DESECSTACK_DOMAIN"]}/api/v1/',
        headers={'Accept-Encoding': 'Accept-Encoding: gzip, deflate'},
    )


@pytest.mark.parametrize("path", ["", "index.html", "index.htm", "confirm/"])
def test_webapp_available(api_anon, path):
    assert api_anon.get(f'https://desec.{os.environ["DESECSTACK_DOMAIN"]}/{path}').status_code == 200
