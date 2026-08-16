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
        """
        with transaction.atomic():
            check = domain.current_delegation_check
            if check is not None and check.agrees_with(result):
                check.save(update_fields=["checked"])  # auto_now bumps it
                return check

            check = self.create(domain=domain, **asdict(result))
            domain.current_delegation_check = check
            domain.save(update_fields=["current_delegation_check"])
            return check


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
