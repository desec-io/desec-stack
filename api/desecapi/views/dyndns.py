import base64
import binascii
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
from desecapi.models import Domain
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.permissions import TokenHasDomainDynDNSPermission
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import RRsetSerializer


class DynDNS12UpdateView(generics.GenericAPIView):
    authentication_classes = (
        TokenAuthentication,
        BasicTokenAuthentication,
        URLParamAuthentication,
    )
    permission_classes = (TokenHasDomainDynDNSPermission,)
    renderer_classes = [PlainTextRenderer]
    serializer_class = RRsetSerializer
    throttle_scope = "dyndns"

    @property
    def throttle_scope_bucket(self):
        return self.domain.name

    def _find_ip(self, param_keys, separator):
        # Check URL parameters
        for param_key in param_keys:
            try:
                params = {
                    param.strip()
                    for param in self.request.query_params[param_key].split(",")
                    if separator in param or param.strip() in ("", "preserve")
                }
            except KeyError:
                continue
            if len(params) > 1 and params & {"", "preserve"}:
                raise ValidationError(
                    detail={
                        "detail": f'IP parameter "{param_key}" cannot have addresses and "preserve" at the same time.',
                        "code": "inconsistent-parameter",
                    }
                )
            if params:
                return [] if "" in params else list(params)

        # Check remote IP address
        client_ip = self.request.META.get("REMOTE_ADDR")
        if separator in client_ip:
            return [client_ip]

        # give up
        return []

    @cached_property
    def qname(self):
        # hostname / host_id
        for param, reserved in {
            "hostname": ["", "YES"],
            "host_id": [],
        }.items():
            try:
                domain_name = self.request.query_params[param]
            except KeyError:
                pass
            else:
                if domain_name not in reserved:
                    return domain_name.lower()

        # http basic auth username
        try:
            domain_name = (
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
            if domain_name and "@" not in domain_name:
                return domain_name.lower()

        # username parameter
        try:
            return self.request.query_params["username"].lower()
        except KeyError:
            pass

        # only domain associated with this user account
        try:
            return self.request.user.domains.get().name
        except Domain.MultipleObjectsReturned:
            raise ValidationError(
                detail={
                    "detail": "Request does not properly specify domain for update.",
                    "code": "domain-unspecified",
                }
            )

    @cached_property
    def domain(self):
        try:
            return Domain.objects.filter_qname(
                self.qname, owner=self.request.user
            ).order_by("-name_length")[0]
        except (IndexError, ValueError, Domain.DoesNotExist):
            metrics.get("desecapi_dynDNS12_domain_not_found").inc()
            raise NotFound("nohost")

    @property
    def subname(self):
        return self.qname.rpartition(f".{self.domain.name}")[0]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "domain": self.domain,
            "minimum_ttl": 60,
        }

    def get_queryset(self):
        return self.domain.rrset_set.filter(
            subname=self.subname, type__in=["A", "AAAA"]
        )

    def get(self, request, *args, **kwargs):
        instances = self.get_queryset().all()

        record_params = {
            "A": self._find_ip(["myip", "myipv4", "ip"], separator="."),
            "AAAA": self._find_ip(["myipv6", "ipv6", "myip", "ip"], separator=":"),
        }

        data = [
            {
                "type": type_,
                "subname": self.subname,
                "ttl": 60,
                "records": ip_params,
            }
            for type_, ip_params in record_params.items()
            if "preserve" not in ip_params
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

        with PDNSChangeTracker():
            serializer.save()

        return Response("good", content_type="text/plain")
