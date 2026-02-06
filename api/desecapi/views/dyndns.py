import base64
import binascii
from collections import defaultdict
from functools import cached_property

from rest_framework import generics
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings

from desecapi import metrics
from desecapi.authentication import (
    BasicTokenAuthentication,
    TokenAuthentication,
    URLParamAuthentication,
)
from desecapi.exceptions import ConcurrencyException
from desecapi.models import Domain, RR, replace_ip_subnet
from desecapi.pdns_change_tracker import NSLordChangeTracker
from desecapi.permissions import IsDomainOwner
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import RRsetSerializer


from dataclasses import dataclass
from ipaddress import ip_network, IPv4Network, IPv6Network


@dataclass
class SetIPs:
    """Represents the action of setting specific IP addresses."""

    ips: list[str]


@dataclass
class UpdateWithSubnet:
    """Represents the action of updating IPs with a subnet."""

    subnet: IPv4Network | IPv6Network


@dataclass
class PreserveIPs:
    """Represents the action of leaving the IPs untouched."""

    pass


UpdateAction = SetIPs | UpdateWithSubnet | PreserveIPs


class DynDNS12UpdateView(generics.GenericAPIView):
    authentication_classes = (
        TokenAuthentication,
        BasicTokenAuthentication,
        URLParamAuthentication,
    )
    permission_classes = (IsDomainOwner,)
    renderer_classes = [PlainTextRenderer]
    serializer_class = RRsetSerializer
    throttle_scope = "dyndns"

    @property
    def throttle_scope_bucket(self):
        return self.domain.name

    def _find_action(self, param_keys, separator) -> UpdateAction:
        """
        Parses the request for IP parameters and determines the appropriate update action.

        This method checks a given list of parameter keys in the request URL. It handles
        plain IP addresses, comma-separated lists of IPs, the "preserve" keyword, and
        subnet notation (e.g., "10.0.0.0/24"). It also uses the client's remote IP
        as a fallback.

        Returns:
            UpdateAction: A dataclass instance (`SetIPs`, `UpdateWithSubnet`, or `PreserveIPs`)
            representing the action to be taken.
        """
        # Check URL parameters
        for param_key in param_keys:
            try:
                params = set(
                    filter(
                        lambda param: separator in param or param in ("", "preserve"),
                        map(str.strip, self.request.query_params[param_key].split(",")),
                    )
                )
            except KeyError:
                continue
            if not params:
                continue

            try:
                (param,) = params  # unpacks if params has exactly one element
            except ValueError:  # more than one element
                if params & {"", "preserve"}:
                    raise ValidationError(
                        detail=f'IP parameter "{param_key}" cannot have addresses and "preserve" or an empty value at the same time.',
                        code="inconsistent-parameter",
                    )
                if any("/" in param for param in params):
                    raise ValidationError(
                        detail=f'IP parameter "{param_key}" cannot use subnet notation with multiple addresses.',
                        code="multiple-subnet",
                    )
            else:  # one element
                match param:
                    case "":
                        return SetIPs(ips=[])
                    case "preserve":
                        return PreserveIPs()
                    case str(x) if "/" in x:
                        try:
                            subnet = ip_network(param, strict=False)
                            return UpdateWithSubnet(subnet=subnet)
                        except ValueError as e:
                            raise ValidationError(
                                detail=f'IP parameter "{param_key}" is an invalid subnet: {e}',
                                code="invalid-subnet",
                            )

            return SetIPs(ips=list(params))

        # Check remote IP address
        client_ip = self.request.META.get("REMOTE_ADDR")
        if separator in client_ip:
            return SetIPs(ips=[client_ip])

        # give up
        return SetIPs(ips=[])

    @staticmethod
    def _sanitize_qnames(qnames_str) -> set[str]:
        qnames = qnames_str.lower().split(",")
        return {name.strip() for name in qnames}

    @cached_property
    def qnames(self) -> set[str]:
        # hostname / host_id
        for param, reserved in {
            "hostname": ["", "YES"],
            "host_id": [],
        }.items():
            try:
                domain_names = self.request.query_params[param]
            except KeyError:
                pass
            else:
                if domain_names not in reserved:
                    return self._sanitize_qnames(domain_names)

        # http basic auth username
        try:
            domain_names = (
                base64.b64decode(
                    get_authorization_header(self.request)
                    .decode()
                    .split(" ")[1]
                    .encode()
                )
                .decode()
                .split(":")[0]
            )
        except (binascii.Error, IndexError, UnicodeDecodeError):
            pass
        else:
            if domain_names and "@" not in domain_names:
                return self._sanitize_qnames(domain_names)

        # username parameter
        try:
            domain_names = self.request.query_params["username"]
            return self._sanitize_qnames(domain_names)
        except KeyError:
            pass

        # only domain associated with this user account
        try:
            return {self.request.user.domains.get().name}
        except Domain.MultipleObjectsReturned:
            raise ValidationError(
                detail={
                    "detail": "Request does not properly specify domain for update.",
                    "code": "domain-unspecified",
                }
            )

    @cached_property
    def domain(self) -> Domain:
        qname_qs = (
            Domain.objects.filter_qname(qname, owner=self.request.user)
            for qname in self.qnames
        )
        domains = (
            Domain.objects.none()
            .union(*(qs.order_by("-name_length")[:1] for qs in qname_qs), all=True)
            .all()
        )

        if len(domains) != len(self.qnames):
            metrics.get("desecapi_dynDNS12_domain_not_found").inc()
            raise NotFound("nohost")

        if len({d.pk for d in domains}) > 1:
            raise ValidationError(
                detail={
                    "detail": "Cannot update subdomains from more than one domain.",
                    "code": "cross-domain-update",
                }
            )

        return domains[0]

    @property
    def subnames(self) -> list[str]:
        return [qname.rpartition(f".{self.domain.name}")[0] for qname in self.qnames]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "domain": self.domain,
            "minimum_ttl": 60,
        }

    def get_queryset(self):
        return self.domain.rrset_set.filter(
            subname__in=self.subnames, type__in=["A", "AAAA"]
        ).prefetch_related("records")

    @staticmethod
    def _get_records(records: list[RR], action: UpdateAction) -> list[str] | None:
        """
        Determines the final list of IP address records based on the given action.

        Args:
            records (list): A list of RR objects (for one RRset).
            action (UpdateAction): The action to perform.

        Returns:
            list or None: A list of IP address strings, or None if the records should be preserved.
        """
        match action:
            case SetIPs():
                return action.ips
            case UpdateWithSubnet():
                return replace_ip_subnet(records, action.subnet)
            case PreserveIPs():
                return None

    def get(self, request, *args, **kwargs) -> Response:
        instances = self.get_queryset()

        subname_records = defaultdict(list)
        for rrset in instances:
            subname_records[rrset.subname].extend(rrset.records.all())

        actions = {
            "A": self._find_action(["myip", "myipv4", "ip"], separator="."),
            "AAAA": self._find_action(["myipv6", "ipv6", "myip", "ip"], separator=":"),
        }

        data = [
            {
                "type": type_,
                "subname": subname,
                "ttl": 60,
                "records": records,
            }
            for subname in self.subnames
            for type_, action in actions.items()
            if (records := self._get_records(subname_records[subname], action))
            is not None
        ]

        serializer = self.get_serializer(instances, data=data, many=True, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            if any(
                any(
                    getattr(non_field_error, "code", "") == "unique"
                    for non_field_error in err.get(
                        api_settings.NON_FIELD_ERRORS_KEY, []
                    )
                )
                for err in e.detail
            ):
                raise ConcurrencyException from e
            raise e
        with NSLordChangeTracker():
            serializer.save()

        return Response("good", content_type="text/plain")
