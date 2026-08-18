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
from django.db.models import Q
from django.utils import timezone

from desecapi import delegation, logger, unbound
from desecapi.models import DelegationCheck, Domain


BULK_QUEUE = "delegation_bulk"
ADHOC_QUEUE = "delegation_adhoc"


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
