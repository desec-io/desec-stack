from django.core.management import BaseCommand, CommandError

from desecapi import knot, pdns
from desecapi.exceptions import PDNSException
from desecapi.models import Domain
from desecapi.pdns_change_tracker import PDNSChangeTracker
from django.db import transaction


class Command(BaseCommand):
    help = "Sync RRsets from local API database to pdns."

    def add_arguments(self, parser):
        parser.add_argument(
            "domain-name",
            nargs="*",
            help="Domain name to sync. If omitted, will import all API domains.",
        )

    def handle(self, *args, **options):
        domains = Domain.objects.all()

        if options["domain-name"]:
            domains = domains.filter(name__in=options["domain-name"])
            domain_names = domains.values_list("name", flat=True)

            for domain_name in options["domain-name"]:
                if domain_name not in domain_names:
                    raise CommandError("{} is not a known domain".format(domain_name))

        for domain in domains:
            self.stdout.write("%s ..." % domain.name, ending="")
            try:
                self._sync_domain(domain)
                self.stdout.write(" synced")
            except Exception as e:
                self.stdout.write(" failed")
                msg = "Error while processing {}: {}".format(domain.name, e)
                raise CommandError(msg)

    @staticmethod
    @transaction.atomic
    def _sync_domain(domain):
        # Create domain on pdns/knot if it does not exist
        try:
            PDNSChangeTracker.CreateDomain(domain_name=domain.name).pdns_do()
        except PDNSException as e:
            # Domain already exists on nslord
            if e.response.status_code == 409:
                pass
            else:
                raise e

        # modifications actually merged with additions in CreateUpdateDeleteRRSets
        modifications = {
            (rrset.type, rrset.subname) for rrset in domain.rrset_set.all()
        }
        deletions = {
            (rrset["type"], rrset["subname"]) for rrset in pdns.get_rrset_datas(domain)
        } - modifications
        deletions.discard(("SOA", ""))  # do not remove SOA record

        # Update zone on nslord, then trigger retrieval on nsmaster (Knot)
        PDNSChangeTracker.CreateUpdateDeleteRRSets(
            domain.name, set(), modifications, deletions
        ).pdns_do()
        knot.retrieve_zone(domain.name)
