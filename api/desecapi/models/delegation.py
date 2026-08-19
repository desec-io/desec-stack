from dataclasses import asdict

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django_prometheus.models import ExportModelOperationsMixin

from .domains import Domain


class DelegationCheckManager(models.Manager):
    def record(self, domain, result):
        """
        Records the outcome of a check as a change log entry: when it agrees
        with the domain's current state, only the confirmation time is bumped;
        otherwise, a new row begins a new state.

        Also maintains Domain.secure_delegation_since, which unlike the change
        log ignores checks that failed -- see _secure_since().
        """
        with transaction.atomic():
            check = domain.current_delegation_check
            agrees = check is not None and check.agrees_with(result)

            if agrees:
                check.save(update_fields=["checked"])  # auto_now bumps it
                update_fields = set()
            else:
                check = self.create(domain=domain, **asdict(result))
                domain.current_delegation_check = check
                update_fields = {"current_delegation_check"}

            since = self._secure_since(domain, result, check)
            if since != domain.secure_delegation_since:
                domain.secure_delegation_since = since
                update_fields.add("secure_delegation_since")

            if update_fields:
                domain.save(update_fields=update_fields)
            return check

    @staticmethod
    def _secure_since(domain, result, check):
        """
        Returns the domain's new secure_delegation_since value.

        A check that could not be carried out says nothing about the domain, so
        it must not clear the field: an outage on our side is ours, not the
        user's. Everything else is a statement about the domain and does update
        it, including the negative ones. The original transition time is
        preserved as long as the domain stays secure, so the field reads as
        "secure since", not "last seen secure".
        """
        if (
            result.security_status == DelegationCheck.SecurityStatus.ERROR
            or result.nameserver_status == DelegationCheck.NameserverStatus.ERROR
        ):
            return domain.secure_delegation_since

        secure = result.security_status == DelegationCheck.SecurityStatus.SECURE and (
            result.nameserver_status
            in (
                DelegationCheck.NameserverStatus.CORRECTLY_DELEGATED,
                # A multi-signer setup that has us among its providers is work
                # the user did, and the zone is validly signed either way.
                DelegationCheck.NameserverStatus.MULTI_PROVIDER,
            )
        )
        return (domain.secure_delegation_since or check.created) if secure else None


class DelegationCheck(ExportModelOperationsMixin("DelegationCheck"), models.Model):
    # Stored as integers, like Domain.RenewalState. Where a name is wanted --
    # Prometheus labels, later API output -- it comes from .name or .label, so
    # the stored representation stays an implementation detail.
    class SecurityStatus(models.IntegerChoices):
        SECURE = 0
        INSECURE = 1
        MISCONFIGURED = 2
        ERROR = 3

    class NameserverStatus(models.IntegerChoices):
        CORRECTLY_DELEGATED = 0
        MULTI_PROVIDER = 1
        OTHER_PROVIDER = 2
        NOT_DELEGATED = 3
        ERROR = 4

    domain = models.ForeignKey(
        Domain, on_delete=models.CASCADE, related_name="delegation_checks"
    )
    created = models.DateTimeField(auto_now_add=True)  # when this state began
    checked = models.DateTimeField(auto_now=True)  # when it was last confirmed
    security_status = models.IntegerField(choices=SecurityStatus.choices)
    nameserver_status = models.IntegerField(choices=NameserverStatus.choices)
    nameservers = ArrayField(models.CharField(max_length=255), default=list)
    ede_code = models.PositiveSmallIntegerField(null=True)
    ede_text = models.TextField(blank=True)
    rcode = models.PositiveSmallIntegerField(null=True)

    objects = DelegationCheckManager()

    class Meta:
        ordering = ("created",)

    def agrees_with(self, result):
        # Only the two status dimensions and the NS set constitute the state;
        # a changed EDE text or rcode does not start a new one.
        return (
            self.security_status == result.security_status
            and self.nameserver_status == result.nameserver_status
            and self.nameservers == result.nameservers
        )

    def __str__(self):
        return (
            f"{self.domain}: {self.get_security_status_display()}, "
            f"{self.get_nameserver_status_display()}"
        )
