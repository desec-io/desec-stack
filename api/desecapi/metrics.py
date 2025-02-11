from prometheus_client import Counter, Histogram

metrics = {}


def get(name):
    return metrics.get(name)


def set_counter(name, *args, **kwargs):
    metrics[name] = Counter(name, *args, **kwargs)


def set_histogram(name, *args, **kwargs):
    metrics[name] = Histogram(name, *args, **kwargs)


# models metrics
set_counter(
    "desecapi_captcha_content_created",
    "number of times captcha content created",
    ["kind"],
)
set_counter("desecapi_autodelegation_created", "number of autodelegations added")
set_counter("desecapi_autodelegation_deleted", "number of autodelegations deleted")
set_histogram(
    "desecapi_messages_queued",
    "number of emails queued",
    ["reason", "user", "lane"],
    buckets=[0, 1, float("inf")],
)

# views metrics
set_counter(
    "desecapi_dynDNS12_domain_not_found", "number of times dynDNS12 domain is not found"
)

# crypto.py metrics
set_counter(
    "desecapi_key_encryption_success",
    "number of times key encryption was successful",
    ["context"],
)
set_counter(
    "desecapi_key_decryption_success",
    "number of times key decryption was successful",
    ["context"],
)

# serializers metrics
set_counter(
    "desecapi_records_serializer_validate_length",
    "number of attempts to provision an overly long RRset",
)
set_counter(
    "desecapi_records_serializer_validate_blocked_subnet",
    "number of attempts to provision addresses from a blocked subnet",
    ["blocked_subnet"],
)

# exception_handlers.py metrics
set_counter(
    "desecapi_exception",
    "number of times an exception was raised",
    ["exception_class"],
)

# pdns.py metrics
set_counter(
    "desecapi_pdns_request_success",
    "number of times pdns request was successful",
    ["method", "status"],
)
set_counter(
    "desecapi_pdns_request_failure",
    "number of times pdns request failed",
    ["method", "path", "status"],
)
set_counter("desecapi_pdns_keys_fetched", "number of times pdns keys were fetched")

# pch.py metrics
set_counter(
    "desecapi_pch_request_success",
    "number of times PCH request was successful",
    ["method", "status"],
)
set_counter(
    "desecapi_pch_request_failure",
    "number of times PCH request failed",
    ["method", "path", "status"],
)


# pdns_change_tracker.py metrics
set_counter(
    "desecapi_pdns_catalog_updated",
    "number of times pdns catalog was updated successfully",
)

# throttling.py metrics
set_counter(
    "desecapi_throttle_failure",
    "number of requests throttled",
    ["method", "scope", "user", "bucket"],
)
