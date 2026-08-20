import dns.name
import dns.zone
from django.conf import settings
from rest_framework import serializers

from desecapi.models import Domain, RR_SET_TYPES_AUTOMATIC
from desecapi.validators import ReadOnlyOnUpdateValidator

from .records import RRsetSerializer


class DomainSerializer(serializers.ModelSerializer):
    default_error_messages = {
        **serializers.Serializer.default_error_messages,
        "name_unavailable": "This domain name conflicts with an existing domain, or is disallowed by policy.",
    }
    zonefile = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Domain
        fields = (
            "created",
            "published",
            "name",
            "keys",
            "minimum_ttl",
            "touched",
            "zonefile",
        )
        read_only_fields = (
            "published",
            "minimum_ttl",
        )
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
        delegation_error = domain.delegation_error()
        if delegation_error is not None:
            raise serializers.ValidationError(
                delegation_error, code="delegation_impossible"
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

    def validate_delegation_points(self, domain_name: str):
        """
        Rejects an imported zone that occupies the delegation point of a domain which the
        new domain will delegate, the counterpart of Domain.delegation_error().
        """
        domain = Domain(name=domain_name, owner=self.context["request"].user)
        zone_name = dns.name.from_text(domain_name)
        for child in domain.delegated_children():
            subname = domain.delegation_subname(child.name)
            node = self.import_zone.get_node(
                dns.name.from_text(subname, origin=zone_name)
            )
            if node is not None and node.get_rdataset(
                dns.rdataclass.IN, dns.rdatatype.CNAME
            ):
                raise serializers.ValidationError(
                    {
                        "zonefile": [
                            f"Cannot delegate {child.name} in {domain_name}: there is a "
                            f"CNAME record at this name."
                        ]
                    },
                    code="delegation_impossible",
                )

    def validate(self, attrs):
        if attrs.get("zonefile") is not None:
            self.parse_zonefile(attrs.get("name"), attrs.pop("zonefile"))
            self.validate_delegation_points(attrs["name"])
        return super().validate(attrs)

    def create(self, validated_data):
        # save domain
        domain: Domain = super().create(validated_data)

        # save RRsets if zonefile was given
        nodes = getattr(self.import_zone, "nodes", None)
        if nodes:
            zone_name = dns.name.from_text(validated_data["name"])
            min_ttl, max_ttl = domain.minimum_ttl, settings.MAXIMUM_TTL
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
