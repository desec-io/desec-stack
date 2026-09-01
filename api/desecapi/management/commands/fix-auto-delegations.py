from functools import partial

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from desecapi.models import Domain, RR, RRset
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):
    help = (
        "Adds missing and removes stale automatic delegations. Considers all domains unless "
        "domain names are given; each name is considered both as a delegating and as a "
        "delegated domain. Reads the DNSSEC keys of every delegated domain from pdns, so "
        "giving names is much cheaper than checking everything. Only reports what would "
        "change, unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("names", nargs="*", help="Domain name(s) to check")
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Perform the changes instead of only reporting them",
        )

    def handle(self, *args, **options):
        names = options["names"]
        if names:
            parents = list(Domain.objects.filter(name__in=names))
            unknown = set(names) - {domain.name for domain in parents}
            if unknown:
                raise CommandError("Unknown domain(s): %s" % ", ".join(sorted(unknown)))
            # A given name is considered both as a delegating and as a delegated domain
            children = {domain.name: domain for domain in parents}
            for domain in parents:
                children |= {child.name: child for child in domain.delegated_children()}
            children = list(children.values())
        else:
            parents = children = Domain.objects.all()

        actions = [
            *self._missing_delegations(children),
            *self._stale_delegations(parents),
        ]
        for description, action in actions:
            print(description)
            if options["apply"]:
                PDNSChangeTracker.track(action)
        print(
            "%d delegation(s) %s"
            % (len(actions), "fixed" if options["apply"] else "to fix")
        )

    @staticmethod
    def _contents(domain, subname, type_):
        try:
            rrset = domain.rrset_set.get(subname=subname, type=type_)
        except RRset.DoesNotExist:
            return set()
        return {rr.content for rr in rrset.records.all()}

    @classmethod
    def _missing_delegations(cls, domains):
        for domain in domains:
            parent = domain.delegation_parent
            if parent is None:
                continue
            ds = [
                RR.canonical_presentation_format(content, "DS")
                for content in domain.ds_contents
            ]
            subname = parent.delegation_subname(domain.name)
            missing = {
                type_: set(contents) - cls._contents(parent, subname, type_)
                for type_, contents in [("NS", settings.DEFAULT_NS), ("DS", ds)]
            }
            if any(missing.values()):
                yield (
                    "%s: add delegation of %s (%s)"
                    % (
                        parent.name,
                        domain.name,
                        ", ".join(
                            f"{type_}: {' '.join(sorted(contents))}"
                            for type_, contents in missing.items()
                            if contents
                        ),
                    ),
                    partial(parent.add_delegation, domain.name, ds),
                )

    @classmethod
    def _stale_delegations(cls, domains):
        default_ns = {
            RR.canonical_presentation_format(content, "NS")
            for content in settings.DEFAULT_NS
        }
        for parent in domains:
            for subname in (
                parent.rrset_set.filter(type="NS")
                .exclude(subname="")
                # Wildcards cannot be delegations; leave grandfathered ones alone
                .exclude(subname__startswith="*")
                .values_list("subname", flat=True)
            ):
                if not default_ns & cls._contents(parent, subname, "NS"):
                    continue
                child_name = f"{subname}.{parent.name}"
                child = Domain.objects.filter(name=child_name).first()
                if child is not None and child.delegation_parent == parent:
                    continue
                yield (
                    "%s: remove delegation of %s" % (parent.name, child_name),
                    partial(
                        parent.remove_delegation,
                        child_name,
                        [] if child is None else child.ds_contents,
                    ),
                )
