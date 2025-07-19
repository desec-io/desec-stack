from __future__ import annotations

import binascii
import uuid
from ipaddress import ip_address, ip_network, IPv4Network, IPv6Network

import dns
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.core import validators
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Manager
from django.db.models.expressions import RawSQL
from django_prometheus.models import ExportModelOperationsMixin
from dns import rdataclass, rdatatype
from dns.rdtypes import ANY, IN

from desecapi import pdns
from desecapi.dns import AAAA, CERT, CNAME, LongQuotedTXT, MX, NS, SRV

from .base import validate_lower, validate_upper


# RR set types: the good, the bad, and the ugly
# known, but unsupported types
RR_SET_TYPES_UNSUPPORTED = {
    "ALIAS",  # Requires signing at the frontend, hence unsupported in desec-stack
    "IPSECKEY",  # broken in pdns, https://github.com/PowerDNS/pdns/issues/10589 TODO enable with pdns auth >= 4.7.0
    "KEY",  # Application use restricted by RFC 3445, DNSSEC use replaced by DNSKEY and handled automatically
    "WKS",  # General usage not recommended, "SHOULD NOT" be used in SMTP (RFC 1123)
}
# restricted types are managed in use by the API, and cannot directly be modified by the API client
RR_SET_TYPES_AUTOMATIC = {
    # corresponding functionality is automatically managed:
    "KEY",
    "NSEC",
    "NSEC3",
    "OPT",
    "RRSIG",
    # automatically managed by the API:
    "NSEC3PARAM",
    "SOA",
}
# backend types are types that are the types supported by the backend(s)
RR_SET_TYPES_BACKEND = pdns.SUPPORTED_RRSET_TYPES
# validation types are types supported by the validation backend, currently: dnspython
RR_SET_TYPES_VALIDATION = (
    set(ANY.__all__) | set(IN.__all__) | {"L32", "L64", "LP", "NID"}
)  # https://github.com/rthalley/dnspython/pull/751
# manageable types are directly managed by the API client
RR_SET_TYPES_MANAGEABLE = (
    (RR_SET_TYPES_BACKEND & RR_SET_TYPES_VALIDATION)
    - RR_SET_TYPES_UNSUPPORTED
    - RR_SET_TYPES_AUTOMATIC
)


def replace_ip_subnet(records, subnet):
    """
    Takes a list of A or AAAA records and returns them with their subnet bits replaced accordingly.
    """
    return [
        str(
            ip_address(int(ip_address(record.content)) & int(subnet.hostmask))  # suffix
            + int(subnet.network_address)  # prefix
        )
        for record in records
        if type(ip_address(record.content)) is type(subnet.network_address)
    ]


class RRsetManager(Manager):
    def create(self, contents=None, **kwargs):
        rrset = super().create(**kwargs)
        for content in contents or []:
            RR.objects.create(rrset=rrset, content=content)
        return rrset


class RRset(ExportModelOperationsMixin("RRset"), models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    touched = models.DateTimeField(auto_now=True, db_index=True)
    domain = models.ForeignKey("Domain", on_delete=models.CASCADE)
    subname = models.CharField(
        max_length=178,
        blank=True,
        validators=[
            validate_lower,
            validators.RegexValidator(
                regex=r"^([*]|(([*][.])?([a-z0-9_-]{1,63}[.])*[a-z0-9_-]{1,63}))$",
                message="Subname can only use (lowercase) a-z, 0-9, ., -, and _, "
                "may start with a '*.', or just be '*'. Components may not exceed 63 characters.",
                code="invalid_subname",
            ),
        ],
    )
    type = models.CharField(
        max_length=10,
        validators=[
            validate_upper,
            validators.RegexValidator(
                regex=r"^[A-Z][A-Z0-9]*$",
                message="Type must be uppercase alphanumeric and start with a letter.",
                code="invalid_type",
            ),
        ],
    )
    ttl = models.PositiveIntegerField()

    objects = RRsetManager()

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="cname_exclusivity",
                expressions=[
                    ("domain", RangeOperators.EQUAL),
                    ("subname", RangeOperators.EQUAL),
                    (RawSQL("int4(type = 'CNAME')", ()), RangeOperators.NOT_EQUAL),
                ],
            ),
        ]
        unique_together = (("domain", "subname", "type"),)

    @staticmethod
    def construct_name(subname, domain_name):
        return ".".join(filter(None, [subname, domain_name])) + "."

    @property
    def name(self):
        return self.construct_name(self.subname, self.domain.name)

    def save(self, *args, **kwargs):
        # TODO Enforce that subname and type aren't changed. https://github.com/desec-io/desec-stack/issues/553
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def clean_records(self, records_presentation_format):
        """
        Validates the records belonging to this set. Validation rules follow the DNS specification; some types may
        incur additional validation rules.

        Raises ValidationError if violation of DNS specification is found.

        Returns a set of records in canonical presentation format.

        :param records_presentation_format: iterable of records in presentation format
        """
        errors = []

        # Singletons
        if self.type in (
            "CNAME",
            "DNAME",
        ):
            if len(records_presentation_format) > 1:
                errors.append(f"{self.type} RRset cannot have multiple records.")

        # Non-apex
        if self.type in (
            "CNAME",
            "DS",
        ):
            if self.subname == "":
                errors.append(f"{self.type} RRset cannot have empty subname.")

        if self.type in ("DNSKEY",):
            if self.subname != "":
                errors.append(f"{self.type} RRset must have empty subname.")

        def _error_msg(record, detail):
            return f"Record content of {self.type} {self.name} invalid: '{record}': {detail}"

        records_canonical_format = set()
        for r in records_presentation_format:
            try:
                r_canonical_format = RR.canonical_presentation_format(r, self.type)
            except ValueError as ex:
                errors.append(_error_msg(r, str(ex)))
            else:
                if r_canonical_format in records_canonical_format:
                    errors.append(
                        _error_msg(
                            r,
                            f"Duplicate record content: this is identical to "
                            f"'{r_canonical_format}'",
                        )
                    )
                else:
                    records_canonical_format.add(r_canonical_format)

        if any(errors):
            raise ValidationError(errors)

        return records_canonical_format

    def save_records(self, records):
        """
        Updates this RR set's resource records, discarding any old values.

        Records are expected in presentation format and are converted to canonical
        presentation format (e.g., 127.00.0.1 will be converted to 127.0.0.1).
        Raises if a invalid set of records is provided.

        This method triggers the following database queries:
        - one DELETE query
        - one SELECT query for comparison of old with new records
        - one INSERT query, if one or more records were added

        Changes are saved to the database immediately.

        :param records: list of records in presentation format
        """
        new_records = self.clean_records(records)

        # Delete RRs that are not in the new record list from the DB
        self.records.exclude(content__in=new_records).delete()  # one DELETE

        # Retrieve all remaining RRs from the DB
        unchanged_records = set(r.content for r in self.records.all())  # one SELECT

        # Save missing RRs from the new record list to the DB
        added_records = new_records - unchanged_records
        rrs = [RR(rrset=self, content=content) for content in added_records]
        RR.objects.bulk_create(rrs)  # One INSERT

    def __str__(self):
        return "<RRSet %s domain=%s type=%s subname=%s>" % (
            self.pk,
            self.domain.name,
            self.type,
            self.subname,
        )


class RRManager(Manager):
    def bulk_create(self, rrs, **kwargs):
        ret = super().bulk_create(rrs, **kwargs)

        # For each rrset, save once to set RRset.updated timestamp and trigger signal for post-save processing
        rrsets = {rr.rrset for rr in rrs}
        for rrset in rrsets:
            rrset.save()

        return ret


class RR(ExportModelOperationsMixin("RR"), models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name="records")
    content = models.TextField()

    objects = RRManager()

    _type_map = {
        dns.rdatatype.AAAA: AAAA,  # TODO remove when https://github.com/PowerDNS/pdns/issues/8182 is fixed
        dns.rdatatype.CERT: CERT,  # do DNS name validation the same way as pdns
        dns.rdatatype.CNAME: CNAME,  # do DNS name validation the same way as pdns
        dns.rdatatype.MX: MX,  # do DNS name validation the same way as pdns
        dns.rdatatype.NS: NS,  # do DNS name validation the same way as pdns
        dns.rdatatype.SRV: SRV,  # do DNS name validation the same way as pdns
        dns.rdatatype.TXT: LongQuotedTXT,  # we slightly deviate from RFC 1035 and allow tokens longer than 255 bytes
        dns.rdatatype.SPF: LongQuotedTXT,  # we slightly deviate from RFC 1035 and allow tokens longer than 255 bytes
    }

    @staticmethod
    def canonical_presentation_format(any_presentation_format, type_):
        """
        Converts any valid presentation format for a RR into it's canonical presentation format.
        Raises if provided presentation format is invalid.
        """
        rdtype = rdatatype.from_text(type_)

        try:
            # Convert to wire format, ensuring input validation.
            cls = RR._type_map.get(rdtype, dns.rdata)
            wire = cls.from_text(
                rdclass=rdataclass.IN,
                rdtype=rdtype,
                tok=dns.tokenizer.Tokenizer(any_presentation_format),
                relativize=False,
            ).to_digestable()

            if len(wire) > 64000:
                raise ValidationError(
                    f"Ensure this value has no more than 64000 byte in wire format (it has {len(wire)})."
                )

            parser = dns.wire.Parser(wire, current=0)
            with parser.restrict_to(len(wire)):
                rdata = cls.from_wire_parser(
                    rdclass=rdataclass.IN, rdtype=rdtype, parser=parser
                )

            # Convert to canonical presentation format, disable chunking of records.
            # Exempt types with hardcoded chunksize (prevents "got multiple values for keyword argument 'chunksize'").
            chunksize_exception_types = (
                dns.rdatatype.OPENPGPKEY,
                dns.rdatatype.EUI48,
                dns.rdatatype.EUI64,
            )
            if rdtype in chunksize_exception_types:
                return rdata.to_text()
            else:
                return rdata.to_text(chunksize=0)
        except binascii.Error:
            # e.g., odd-length string
            raise ValueError("Cannot parse hexadecimal or base64 record contents")
        except dns.exception.SyntaxError as e:
            # e.g., A/127.0.0.999
            if "quote" in e.args[0]:
                raise ValueError(
                    f"Data for {type_} records must be given using quotation marks."
                )
            else:
                raise ValueError(
                    f'Record content for type {type_} malformed: {",".join(e.args)}'
                )
        except dns.name.NameTooLong:
            raise ValueError("Hostname must be no longer than 255 characters")
        except dns.name.NeedAbsoluteNameOrOrigin:
            raise ValueError(
                'Hostname must be fully qualified (i.e., end in a dot: "example.com.")'
            )
        except ValueError as ex:
            # e.g., string ("asdf") cannot be parsed into int on base 10
            raise ValueError(f"Cannot parse record contents: {ex}")
        except Exception as e:
            # TODO see what exceptions raise here for faulty input
            raise e

    def __str__(self):
        return "<RR %s %s rr_set=%s>" % (self.pk, self.content, self.rrset.pk)
