import requests
from django.conf import settings

from desecapi import logger, metrics

ALLOW = "allow"  # process the request as usual
DROP = "drop"  # discard the request, but give the client the regular response
REJECT = "reject"  # deny the request, and tell the client so
VERDICTS = (ALLOW, DROP, REJECT)

REASON_MAX_LENGTH = 200


def ask(event, **facts):
    """
    Ask the gatekeeper what to do about a request, described by the given facts, and return its
    verdict.

    The gatekeeper is outside the API's trust boundary: its reasoning is logged, but never
    disclosed to the client, and anything other than a verdict it is asked for is ignored. If no
    verdict can be obtained (service down, timeout, unintelligible answer), the request is allowed.
    """
    payload = {"event": event, **facts}
    duration = metrics.get("desecapi_gatekeeper_request_duration_seconds").labels(event)
    try:
        with duration.time():
            response = requests.post(
                settings.GATEKEEPER_API,
                json=payload,
                headers={"User-Agent": "desecapi"},
                timeout=(0.5, settings.GATEKEEPER_TIMEOUT),
            )
        response.raise_for_status()
        answer = response.json()
        verdict = answer["verdict"]
        if verdict not in VERDICTS:
            raise ValueError(f"unknown verdict: {verdict}")
    except (requests.RequestException, LookupError, TypeError, ValueError) as e:
        logger.warning("Could not obtain gatekeeper verdict for %s: %s", event, e)
        metrics.get("desecapi_gatekeeper_request_failure").labels(event).inc()
        return ALLOW

    metrics.get("desecapi_gatekeeper_verdict").labels(event, verdict).inc()
    if verdict != ALLOW:
        reason = str(answer.get("reason"))[:REASON_MAX_LENGTH]
        logger.warning(
            "Gatekeeper verdict on %s for %s: %s (%s)",
            event,
            facts.get("email"),
            verdict,
            reason,
        )
    return verdict
