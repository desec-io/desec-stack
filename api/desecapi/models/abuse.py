from datetime import date
from ipaddress import IPv4Address, IPv4Network

from django.contrib.postgres.indexes import GistIndex
from django.core.validators import MaxValueValidator
from django.db import models
import dns.resolver
from netfields import CidrAddressField, NetManager


class BlockedSubnet(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    asn = models.PositiveBigIntegerField(validators=[MaxValueValidator(2**32 - 1)])
    subnet = CidrAddressField(unique=True)
    country = models.TextField()
    registry = models.TextField()
    allocation_date = models.DateField()

    objects = NetManager()

    class Meta:
        indexes = (
            GistIndex(fields=("subnet",), opclasses=("inet_ops",), name="subnet_idx"),
        )

    @classmethod
    def from_ip(cls, ip):
        # Fetch IP metadata provided by Team Cymru, https://www.team-cymru.com/ip-asn-mapping
        qname = IPv4Address(ip).reverse_pointer.replace(
            "in-addr.arpa", "origin.asn.cymru.com"
        )
        try:
            answer = dns.resolver.resolve(qname, "TXT")[0]
            parts = str(answer).strip('"').split("|")
        except dns.resolver.LifetimeTimeout:
            # In over a year of operation, there was never a smaller network than /24
            print(f"Could not determine ASN and subnet for {ip}, using 0 and /24")
            parts = ["0", f"{ip}/24", "", "", str(date.today())]
        return cls(
            asn=int(parts[0].strip()),
            subnet=IPv4Network(parts[1].strip(), strict=False),
            country=parts[2].strip(),
            registry=parts[3].strip(),
            allocation_date=date.fromisoformat(parts[4].strip()),
        )
