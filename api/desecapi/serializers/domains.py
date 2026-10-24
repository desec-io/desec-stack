import dns.name
import dns.zone
from django.conf import settings
from rest_framework import serializers

from desecapi.models import RR_SET_TYPES_AUTOMATIC, DelegationCheck, Domain
from desecapi.validators import ReadOnlyOnUpdateValidator

from .records import RRsetSerializer


class DomainStatusSerializer(serializers.Serializer):
    """
    What the delegation checks found for a domain.

    Statuses are the lowercased names of DelegationCheck's choices; the stored
    integers stay an implementation detail. Everything that comes from the
    current check is null until the domain has been checked.
    """

    secure_since = serializers.DateTimeField(
        source="secure_delegation_since", read_only=True
    )
    checked = serializers.SerializerMethodField()
    nameserver_status = serializers.SerializerMethodField()
    security_status = serializers.SerializerMethodField()
    nameservers = serializers.SerializerMethodField()

    @staticmethod
    def get_checked(domain):
        check = domain.current_delegation_check
        return (
            serializers.DateTimeField().to_representation(check.checked)
            if check
            else None
        )

    @staticmethod
    def get_nameserver_status(domain):
        check = domain.current_delegation_check
        return (
            DelegationCheck.NameserverStatus(check.nameserver_status).name.lower()
            if check
            else None
        )

    @staticmethod
    def get_security_status(domain):
        check = domain.current_delegation_check
        if (
            check is None
            # Without a delegation, the check asks about the parent instead
            # (whether it is signed), so the stored value is not a statement
            # about this domain.
            or check.nameserver_status == DelegationCheck.NameserverStatus.NOT_DELEGATED
        ):
            return None
        return DelegationCheck.SecurityStatus(check.security_status).name.lower()

    @staticmethod
    def get_nameservers(domain):
        check = domain.current_delegation_check
        return list(check.nameservers) if check else []


class DomainSerializer(serializers.ModelSerializer):
    default_error_messages = {
        **serializers.Serializer.default_error_messages,
        "name_unavailable": "This domain name conflicts with an existing domain, or is disallowed by policy.",
        "name_too_deep": "Only direct registrations are allowed under {suffix}, such as "
        "example.{suffix}. (Deeper subdomains are possible by creating subdomain records "
        "inside your domain.)",
    }
    zonefile = serializers.CharField(write_only=True, required=False, allow_blank=True)
    minimum_ttl = serializers.IntegerField(
        read_only=True, source="effective_minimum_ttl"
    )
    status = DomainStatusSerializer(source="*", read_only=True)

    class Meta:
        model = Domain
        fields = (
            "created",
            "published",
            "name",
            "keys",
            "minimum_ttl",
            "status",
            "touched",
            "zonefile",
        )
        read_only_fields = ("published",)
        extra_kwargs = {
            "name": {"trim_whitespace": False},
        }

    def __init__(self, *args, include_keys=False, **kwargs):
        self.include_keys = include_keys
        self.import_zone = None
        super().__init__(*args, **kwargs)

    def get_fields(self):
        fields = super().get_fields()
        if not self.include_keys:
            fields.pop("keys")
        fields["name"].validators.append(ReadOnlyOnUpdateValidator())
        return fields

    def validate_name(self, value):
        domain = Domain(name=value, owner=self.context["request"].user)
        if not domain.is_registrable():
            raise serializers.ValidationError(
                self.default_error_messages["name_unavailable"], code="name_unavailable"
            )
        suffix = domain.public_suffix
        if (
            suffix in settings.LOCAL_PUBLIC_SUFFIXES
            and value.count(".") > suffix.count(".") + 1
        ):
            raise serializers.ValidationError(
                self.default_error_messages["name_too_deep"].format(suffix=suffix),
                code="name_too_deep",
            )
        return value

    def parse_zonefile(self, domain_name: str, zonefile: str):
        try:
            self.import_zone = dns.zone.from_text(
                zonefile,
                origin=dns.name.from_text(domain_name),
                allow_include=False,
                check_origin=False,
                relativize=False,
                rfc2308_ttl=True,
            )
        except dns.zonefile.CNAMEAndOtherData:
            raise serializers.ValidationError(
                {
                    "zonefile": [
                        "No other records with the same name are allowed alongside a CNAME record."
                    ]
                }
            )
        except ValueError as e:
            if "has non-origin SOA" in str(e):
                raise serializers.ValidationError(
                    {
                        "zonefile": [
                            f"Zonefile includes an SOA record for a name different from {domain_name}."
                        ]
                    }
                )
            raise e
        except dns.exception.SyntaxError as e:
            try:
                line = str(e).split(":")[1]
                raise serializers.ValidationError(
                    {"zonefile": [f"Zonefile contains syntax error in line {line}."]}
                )
            except IndexError:
                raise serializers.ValidationError(
                    {"zonefile": [f"Could not parse zonefile: {str(e)}"]}
                )

    def validate(self, attrs):
        if attrs.get("zonefile") is not None:
            self.parse_zonefile(attrs.get("name"), attrs.pop("zonefile"))
        return super().validate(attrs)

    def create(self, validated_data):
        # save domain
        domain: Domain = super().create(validated_data)

        # save RRsets if zonefile was given
        nodes = getattr(self.import_zone, "nodes", None)
        if nodes:
            zone_name = dns.name.from_text(validated_data["name"])
            min_ttl, max_ttl = domain.effective_minimum_ttl, settings.MAXIMUM_TTL
            data = [
                {
                    "type": dns.rdatatype.to_text(rrset.rdtype),
                    "ttl": max(min_ttl, min(max_ttl, rrset.ttl)),
                    "subname": (
                        (owner_name - zone_name).to_text()
                        if owner_name - zone_name != dns.name.empty
                        else ""
                    ),
                    "records": [rr.to_text() for rr in rrset],
                }
                for owner_name, node in nodes.items()
                for rrset in node.rdatasets
                if (
                    dns.rdatatype.to_text(rrset.rdtype)
                    not in (
                        RR_SET_TYPES_AUTOMATIC
                        | {  # do not import automatically managed record types
                            "CDS",
                            "CDNSKEY",
                            "DNSKEY",
                        }  # do not import these, as this would likely be unexpected
                    )
                    and not (
                        owner_name - zone_name == dns.name.empty
                        and rrset.rdtype == dns.rdatatype.NS
                    )  # ignore apex NS
                )
            ]

            rrset_list_serializer = RRsetSerializer(
                data=data, context=dict(self.context, domain=domain), many=True
            )
            # The following line raises if data passed validation by dnspython during zone file parsing,
            # but is rejected by validation in RRsetSerializer. See also
            # test_create_domain_zonefile_import_validation
            try:
                rrset_list_serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                if isinstance(e.detail, serializers.ReturnList):
                    # match the order of error messages with the RRsets provided to the
                    # serializer to make sense to the client
                    def fqdn(idx):
                        return (data[idx]["subname"] + "." + domain.name).lstrip(".")

                    raise serializers.ValidationError(
                        {
                            "zonefile": [
                                f"{fqdn(idx)}/{data[idx]['type']}: {err}"
                                for idx, d in enumerate(e.detail)
                                for _, errs in d.items()
                                for err in errs
                            ]
                        }
                    )

                raise e

            rrset_list_serializer.save()

        return domain
