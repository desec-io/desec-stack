from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from desecapi import pdns
from desecapi.exceptions import PDNSException
from desecapi.models import Domain
from desecapi.pdns_change_tracker import PDNSChangeTracker


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

        catalog_alignment = False
        for domain in domains:
            self.stdout.write("%s ..." % domain.name, ending="")
            try:
                created = self._sync_domain(domain)
                if created:
                    self.stdout.write(f" created (was missing) ...", ending="")
                    catalog_alignment = True
                self.stdout.write(" synced")
            except Exception as e:
                self.stdout.write(" failed")
                msg = "Error while processing {}: {}".format(domain.name, e)
                raise CommandError(msg)

        if catalog_alignment:
            call_command("align-catalog-zone")

    @staticmethod
    @transaction.atomic
    def _sync_domain(domain):
        created = False

        # Create domain on pdns if it does not exist
        try:
            PDNSChangeTracker.CreateDomain(domain_name=domain.name).pdns_do()
        except PDNSException as e:
            # Domain already exists
            if e.response.status_code == 409:
                pass
            else:
                raise e
        else:
            created = True

        # modifications actually merged with additions in CreateUpdateDeleteRRSets
        modifications = {
            (rrset.type, rrset.subname) for rrset in domain.rrset_set.all()
        }
        deletions = {
            (rrset["type"], rrset["subname"]) for rrset in pdns.get_rrset_datas(domain)
        } - modifications
        deletions.discard(("SOA", ""))  # do not remove SOA record

        # Update zone on nslord, propagate to nsmaster
        PDNSChangeTracker.CreateUpdateDeleteRRSets(
            domain.name, set(), modifications, deletions
        ).pdns_do()
        pdns._pdns_put(
            pdns.NSMASTER, "/zones/{}/axfr-retrieve".format(pdns.pdns_id(domain.name))
        )

        return created
