import json

import requests
from django.conf import settings

from desecapi import metrics
from desecapi.exceptions import PCHException

_config = {
    "base_url": settings.PCH_API,
    "token": settings.PCH_API_TOKEN,
}


def _pch_request(
    method,
    *,
    path,
    expect_status,
    data=None,
    accept="application/json",
):
    if data is not None:
        data = json.dumps(data)

    headers = {
        "Accept": accept,
        "User-Agent": "desecapi",
        "Authorization": _config["token"],
    }
    r = requests.request(method, _config["base_url"] + path, data=data, headers=headers)
    if r.status_code not in expect_status:
        metrics.get("desecapi_pch_request_failure").labels(
            method, path, r.status_code
        ).inc()
        raise PCHException(response=r)
    metrics.get("desecapi_pch_request_success").labels(method, r.status_code).inc()
    return r


def _post(path, data, **kwargs):
    return _pch_request("post", path=path, data=data, **kwargs)


def _delete(path, data, **kwargs):
    return _pch_request("delete", path=path, data=data, **kwargs)


def create_domains(domains):
    _post("/zones", {"zones": domains}, expect_status=[201])


def delete_domains(domains):
    _delete("/zones", {"zones": domains}, expect_status=[200])
