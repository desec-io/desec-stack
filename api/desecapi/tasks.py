"""
Background delegation checks.

The measurement itself lives in desecapi.delegation and knows nothing about
tasks; this module is only about when checks run, and on whose behalf.

Two queues carry the same per-domain task: a bulk one for runs over the whole
inventory, and an ad-hoc one for checks asked for on a single user's behalf.
That the unit of work is one domain is what makes an ad-hoc check responsive
while a bulk run is in flight: Celery cannot preempt a running task, so there
must not be a long one. With a worker consuming both queues at prefetch 1, the
wait for an ad-hoc check is one domain check, not one bulk run.
"""

from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone

from desecapi import delegation, logger, unbound
from desecapi.models import DelegationCheck, Domain, User


BULK_QUEUE = "delegation_bulk"
ADHOC_QUEUE = "delegation_adhoc"

# How many domains one ad-hoc plan may enqueue, so that a single user with a
# large portfolio cannot monopolize the ad-hoc queue. Least recently checked
# first, so that repeated requests work through the backlog.
MAX_ADHOC_DOMAINS = 20

# Minimum spacing between ad-hoc plans for the same user, so that a
# create/delete loop cannot generate outbound DNS traffic on demand.
ADHOC_COOLDOWN = 60

# How fresh a check has to be for an ad-hoc request to leave it alone.
ADHOC_MAX_AGE = 900


def stale_q(max_age):
    """Q object for domains not checked within the last max_age seconds."""
    threshold = timezone.now() - timedelta(seconds=max_age)
    return Q(current_delegation_check__isnull=True) | Q(
        current_delegation_check__checked__lt=threshold
    )


def enqueue_checks(domain_ids, queue, max_age):
    """Enqueues a check per domain, and returns how many were enqueued."""
    count = 0
    for domain_id in domain_ids:
        check_domain_delegation.apply_async((domain_id, max_age), queue=queue)
        count += 1
    return count


def enqueue_user_delegation_check(user, max_age=ADHOC_MAX_AGE):
    """
    Asks for the user's not-yet-secure domains to be checked, at most once per
    ADHOC_COOLDOWN seconds per user. Returns whether the request was accepted.

    Which domains those are is deliberately not decided here: the set may
    change between enqueueing and running, so the task resolves it when it runs.

    Never raises. Callers sit in the request path, where the response is what
    matters and the check is a nicety: a broker or cache outage must not turn a
    request into a 500. The bulk queue reaches the domain either way.
    """
    try:
        if not cache.add(f"delegation-adhoc-{user.pk}", True, timeout=ADHOC_COOLDOWN):
            return False
        plan_user_delegation_checks.delay(str(user.pk), max_age)
    except Exception:
        logger.exception("Could not enqueue delegation checks for user %s", user.pk)
        return False
    return True


@shared_task(queue=ADHOC_QUEUE, acks_late=True, ignore_result=True)
def plan_user_delegation_checks(user_id, max_age=ADHOC_MAX_AGE):
    """
    Enqueues checks for the domains of one user that are not (or not known to
    be) securely delegated to us. Domains that already are do not need looking
    at: their state can only be lost by a check, and a check that would find it
    lost is the bulk queue's business, not the ad-hoc one's.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return  # deleted between enqueueing and running
    except ValidationError:
        return  # not a uuid; a message from an incompatible producer

    domains = (
        user.domains.exclude_under_local_public_suffix()
        .filter(secure_delegation_since__isnull=True)
        .filter(stale_q(max_age))
        .order_by(F("current_delegation_check__checked").asc(nulls_first=True))
        .values_list("pk", flat=True)[:MAX_ADHOC_DOMAINS]
    )
    enqueue_checks(list(domains), ADHOC_QUEUE, max_age)


@shared_task(queue=BULK_QUEUE, acks_late=True, ignore_result=True)
def check_domain_delegation(domain_id, max_age=0):
    """
    Checks one domain, unless it has been checked within the last max_age
    seconds. That test is repeated here and not only where the task was
    enqueued, because the domain may have been checked in between -- which is
    what makes a duplicate message cost a query instead of a check, and lets a
    bulk run be re-planned while its backlog is still draining.
    """
    try:
        domain = (
            Domain.objects.select_related("current_delegation_check")
            .filter(stale_q(max_age))
            .get(pk=domain_id)
        )
    except Domain.DoesNotExist:
        return  # deleted, or checked by someone else in the meantime

    try:
        result = delegation.check(domain.name)
    except unbound.UnboundException as e:
        # Our resolver is broken, which says nothing about the domain. Failing
        # the task would mail admins once per domain in the backlog, so log and
        # leave the domain for the next bulk run instead.
        logger.warning("Resolver unavailable, skipping %s: %s", domain.name, e)
        return

    DelegationCheck.objects.record(domain, result)
