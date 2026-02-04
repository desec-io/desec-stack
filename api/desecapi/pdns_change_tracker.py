from abc import ABC, abstractmethod
import threading
import time

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.db.transaction import atomic
from django.utils import timezone

from desecapi import knot, pch, pdns
from desecapi.models import RR, RRset, Domain


class BaseChangeTracker(ABC):
    """
    Hooks up to model signals to maintain two sets:

    - `domain_additions`: set of added domains
    - `domain_deletions`: set of deleted domains

    The two sets are guaranteed to be disjoint.

    Hooks up to model signals to maintain exactly three sets per domain:

    - `rr_set_additions`: set of added RR sets
    - `rr_set_modifications`: set of modified RR sets
    - `rr_set_deletions`: set of deleted RR sets

    `additions` and `deletions` are guaranteed to be disjoint:
    - If an item is in the set of additions while being deleted, it is removed from `rr_set_additions`.
    - If an item is in the set of deletions while being added, it is removed from `rr_set_deletions`.
    `modifications` and `deletions` are guaranteed to be disjoint.
    - If an item is in the set of deletions while being modified, an exception is raised.
    - If an item is in the set of modifications while being deleted, it is removed from `rr_set_modifications`.

    Note every change tracker object will track all changes to the model across threading.
    To avoid side-effects, it is recommended that in each Django process, only one change
    tracker is run at a time, i.e. do not use them in parallel (e.g., in a multi-threading
    scenario), do not use them nested.
    """

    _active_change_trackers = 0

    class Change(ABC):
        """
        A reversible, atomic operation against the nslord backend.
        """

        def __init__(self, domain_name):
            self._domain_name = domain_name

        @property
        def domain_name(self):
            return self._domain_name

        @property
        @abstractmethod
        def axfr_required(self):
            raise NotImplementedError()

        @abstractmethod
        def nslord_do(self):
            raise NotImplementedError()

        def pdns_do(self):
            self.nslord_do()

        def api_do(self):
            pass

        def pch_do(self):
            pass

    def __init__(self):
        self._domain_additions = set()
        self._domain_deletions = set()
        self._rr_set_additions = {}
        self._rr_set_modifications = {}
        self._rr_set_deletions = {}
        self._domain_nslord = {}
        self.transaction = None

    @classmethod
    def track(cls, f):
        """
        Execute function f with the change tracker.
        :param f: Function to be tracked for nslord-relevant changes.
        :return: Returns the return value of f.
        """
        with cls():
            return f()

    def _manage_signals(self, method):
        if method not in ["connect", "disconnect"]:
            raise ValueError()
        getattr(post_save, method)(
            self._on_rr_post_save, sender=RR, dispatch_uid=self.__module__
        )
        getattr(post_delete, method)(
            self._on_rr_post_delete, sender=RR, dispatch_uid=self.__module__
        )
        getattr(post_save, method)(
            self._on_rr_set_post_save, sender=RRset, dispatch_uid=self.__module__
        )
        getattr(post_delete, method)(
            self._on_rr_set_post_delete, sender=RRset, dispatch_uid=self.__module__
        )
        getattr(post_save, method)(
            self._on_domain_post_save, sender=Domain, dispatch_uid=self.__module__
        )
        getattr(post_delete, method)(
            self._on_domain_post_delete, sender=Domain, dispatch_uid=self.__module__
        )

    def __enter__(self):
        BaseChangeTracker._active_change_trackers += 1
        assert BaseChangeTracker._active_change_trackers == 1, (
            "Nesting %s is not supported." % self.__class__.__name__
        )
        self._domain_additions = set()
        self._domain_deletions = set()
        self._rr_set_additions = {}
        self._rr_set_modifications = {}
        self._rr_set_deletions = {}
        self._domain_nslord = {}
        self._manage_signals("connect")
        self.transaction = atomic()
        self.transaction.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        BaseChangeTracker._active_change_trackers -= 1
        self._manage_signals("disconnect")

        if exc_type:
            # An exception occurred inside our context, exit db transaction and dismiss nslord changes
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            return

        # TODO introduce two phase commit protocol
        changes = self._compute_changes()
        axfr_required = set()
        deferred_changes = []
        for change in changes:
            change_start = time.monotonic()
            try:
                if isinstance(change, KnotChangeTracker.CreateUpdateDeleteRRSets):
                    deferred_changes.append(change)
                    continue
                print(f"nslord change start: {change}", flush=True)
                change.nslord_do()
                print(
                    f"nslord change done: {change} ({time.monotonic() - change_start:.3f}s)",
                    flush=True,
                )
                change.api_do()
                if settings.PCH_API and not settings.DEBUG:
                    change.pch_do()
                if change.axfr_required:
                    axfr_required.add(change.domain_name)
            except Exception as e:
                self.transaction.__exit__(type(e), e, e.__traceback__)
                exc = ValueError(
                    f"For changes {list(map(str, changes))}, {type(e)} occurred during {change}: {str(e)}"
                )
                raise exc from e

        self.transaction.__exit__(None, None, None)

        for change in deferred_changes:
            change_start = time.monotonic()
            try:
                print(f"nslord change start: {change}", flush=True)
                change.nslord_do()
                print(
                    f"nslord change done: {change} ({time.monotonic() - change_start:.3f}s)",
                    flush=True,
                )
                change.api_do()
                if settings.PCH_API and not settings.DEBUG:
                    change.pch_do()
                if change.axfr_required:
                    axfr_required.add(change.domain_name)
            except Exception as e:
                exc = ValueError(
                    f"For changes {list(map(str, changes))}, {type(e)} occurred during {change}: {str(e)}"
                )
                raise exc from e

        for name in axfr_required:
            nslord = self._nslord_for_domain(name)
            if nslord == Domain.NSLord.KNOT:
                wait_start = time.monotonic()
                print(f"knot wait_for_zone start: {name}", flush=True)
                wait_done = {}

                def _wait():
                    wait_done["result"] = knot.wait_for_zone(name)

                thread = threading.Thread(target=_wait, daemon=True)
                thread.start()
                thread.join(timeout=5.0)
                if thread.is_alive():
                    print(f"knot wait_for_zone timeout: {name}", flush=True)
                else:
                    print(
                        f"knot wait_for_zone done: {name} ({time.monotonic() - wait_start:.3f}s)",
                        flush=True,
                    )
            axfr_start = time.monotonic()
            print(f"pdns axfr_to_master start: {name}", flush=True)
            pdns.axfr_to_master(name)
            print(
                f"pdns axfr_to_master done: {name} ({time.monotonic() - axfr_start:.3f}s)",
                flush=True,
            )
        Domain.objects.filter(name__in=axfr_required).update(published=timezone.now())

    def _nslord_for_domain(self, domain_name):
        nslord = self._domain_nslord.get(domain_name)
        if nslord:
            return nslord
        nslord = (
            Domain.objects.filter(name=domain_name)
            .values_list("nslord", flat=True)
            .first()
        )
        return nslord or Domain.NSLord.PDNS

    @abstractmethod
    def _create_domain_change(self, domain_name, nslord):
        raise NotImplementedError()

    @abstractmethod
    def _delete_domain_change(self, domain_name, nslord):
        raise NotImplementedError()

    @abstractmethod
    def _update_rrsets_change(
        self, domain_name, additions, modifications, deletions, nslord
    ):
        raise NotImplementedError()

    def _compute_changes(self):
        changes = []

        for domain_name in self._domain_deletions:
            # discard any RR set modifications
            self._rr_set_additions.pop(domain_name, None)
            self._rr_set_modifications.pop(domain_name, None)
            self._rr_set_deletions.pop(domain_name, None)

            changes.append(
                self._delete_domain_change(
                    domain_name, self._nslord_for_domain(domain_name)
                )
            )

        for domain_name in self._rr_set_additions.keys() | self._domain_additions:
            nslord = self._nslord_for_domain(domain_name)
            if domain_name in self._domain_additions:
                changes.append(self._create_domain_change(domain_name, nslord))

            additions = self._rr_set_additions.get(domain_name, set())
            modifications = self._rr_set_modifications.get(domain_name, set())
            deletions = self._rr_set_deletions.get(domain_name, set())

            assert not (additions & deletions)
            assert not (modifications & deletions)

            # Due to disjoint guarantees with `deletions`, we have four types of RR sets:
            # (1) purely added RR sets
            # (2) purely modified RR sets
            # (3) added and modified RR sets
            # (4) purely deleted RR sets

            # We send RR sets to nslord if one of the following conditions holds:
            # (a) RR set was added and has at least one RR
            # (b) RR set was modified
            # (c) RR set was deleted

            # Conditions (b) and (c) are already covered in the modifications and deletions list,
            # we filter the additions list to remove newly-added, but empty RR sets
            additions -= {
                (type_, subname)
                for (type_, subname) in additions
                if not RR.objects.filter(
                    rrset__domain__name=domain_name,
                    rrset__type=type_,
                    rrset__subname=subname,
                ).exists()
            }

            if additions | modifications | deletions:
                changes.append(
                    self._update_rrsets_change(
                        domain_name, additions, modifications, deletions, nslord
                    )
                )

        return changes

    def _rr_set_updated(self, rr_set: RRset, deleted=False, created=False):
        if self._rr_set_modifications.get(rr_set.domain.name, None) is None:
            self._rr_set_additions[rr_set.domain.name] = set()
            self._rr_set_modifications[rr_set.domain.name] = set()
            self._rr_set_deletions[rr_set.domain.name] = set()

        self._domain_nslord[rr_set.domain.name] = rr_set.domain.nslord

        additions = self._rr_set_additions[rr_set.domain.name]
        modifications = self._rr_set_modifications[rr_set.domain.name]
        deletions = self._rr_set_deletions[rr_set.domain.name]

        item = (rr_set.type, rr_set.subname)
        match (created, deleted):
            case (True, False):  # created
                additions.add(item)
                # can fail with concurrent deletion request
                assert item not in modifications
                deletions.discard(item)
            case (False, True):  # deleted
                if item in additions:
                    additions.remove(item)
                    modifications.discard(item)
                    # no change to deletions
                else:
                    # item not in additions
                    modifications.discard(item)
                    deletions.add(item)
            case (False, False):  # modified
                # we don't care if item was created or not
                modifications.add(item)
                assert item not in deletions
            case _:
                raise ValueError(
                    "An RR set cannot be created and deleted at the same time."
                )

    def _domain_updated(self, domain: Domain, created=False, deleted=False):
        if not created and not deleted:
            # NOTE that the name must not be changed by API contract with models, hence here no-op for nslord.
            return

        name = domain.name
        additions = self._domain_additions
        deletions = self._domain_deletions
        self._domain_nslord[name] = domain.nslord

        if created and deleted:
            raise ValueError(
                "A domain set cannot be created and deleted at the same time."
            )

        if created:
            if name in deletions:
                deletions.remove(name)
            else:
                additions.add(name)
        elif deleted:
            if name in additions:
                additions.remove(name)
            else:
                deletions.add(name)

    # noinspection PyUnusedLocal
    def _on_rr_post_save(
        self, signal, sender, instance: RR, created, update_fields, raw, using, **kwargs
    ):
        self._rr_set_updated(instance.rrset)

    # noinspection PyUnusedLocal
    def _on_rr_post_delete(self, signal, sender, instance: RR, using, **kwargs):
        try:
            self._rr_set_updated(instance.rrset)
        except RRset.DoesNotExist:
            pass

    # noinspection PyUnusedLocal
    def _on_rr_set_post_save(
        self,
        signal,
        sender,
        instance: RRset,
        created,
        update_fields,
        raw,
        using,
        **kwargs,
    ):
        self._rr_set_updated(instance, created=created)

    # noinspection PyUnusedLocal
    def _on_rr_set_post_delete(self, signal, sender, instance: RRset, using, **kwargs):
        self._rr_set_updated(instance, deleted=True)

    # noinspection PyUnusedLocal
    def _on_domain_post_save(
        self,
        signal,
        sender,
        instance: Domain,
        created,
        update_fields,
        raw,
        using,
        **kwargs,
    ):
        self._domain_updated(instance, created=created)

    # noinspection PyUnusedLocal
    def _on_domain_post_delete(self, signal, sender, instance: Domain, using, **kwargs):
        self._domain_updated(instance, deleted=True)

    def __str__(self):
        all_rr_sets = (
            self._rr_set_additions.keys()
            | self._rr_set_modifications.keys()
            | self._rr_set_deletions.keys()
        )
        all_domains = self._domain_additions | self._domain_deletions
        return (
            "<%s: %i added or deleted domains; %i added, modified or deleted RR sets>"
            % (self.__class__.__name__, len(all_domains), len(all_rr_sets))
        )


class PDNSChangeTracker(BaseChangeTracker):
    class PDNSChange(BaseChangeTracker.Change):
        def pdns_do(self):
            self.nslord_do()

    class CreateDomain(PDNSChange):
        @property
        def axfr_required(self):
            return True

        def nslord_do(self):
            pdns.create_zone_lord(self.domain_name)
            pdns.create_zone_master(self.domain_name)
            pdns.update_catalog(self.domain_name)

        def api_do(self):
            rr_set = RRset(
                domain=Domain.objects.get(name=self.domain_name),
                type="NS",
                subname="",
                ttl=settings.DEFAULT_NS_TTL,
            )
            rr_set.save()

            rrs = [RR(rrset=rr_set, content=ns) for ns in settings.DEFAULT_NS]
            RR.objects.bulk_create(rrs)  # One INSERT

        def pch_do(self):
            pch.create_domains([self.domain_name])

        def __str__(self):
            return "Create Domain %s" % self.domain_name

    class DeleteDomain(PDNSChange):
        @property
        def axfr_required(self):
            return False

        def nslord_do(self):
            pdns.delete_zone_lord(self.domain_name)
            pdns.delete_zone_master(self.domain_name)
            pdns.update_catalog(self.domain_name, delete=True)

        def pch_do(self):
            pch.delete_domains([self.domain_name])

        def __str__(self):
            return "Delete Domain %s" % self.domain_name

    class CreateUpdateDeleteRRSets(PDNSChange):
        def __init__(self, domain_name, additions, modifications, deletions):
            super().__init__(domain_name)
            self._additions = additions
            self._modifications = modifications
            self._deletions = deletions

        @property
        def axfr_required(self):
            return True

        def nslord_do(self):
            data = {
                "rrsets": [
                    {
                        "name": RRset.construct_name(subname, self._domain_name),
                        "type": type_,
                        "ttl": 1,  # some meaningless integer required by pdns's syntax
                        "changetype": "REPLACE",  # don't use "DELETE" due to desec-stack#220, PowerDNS/pdns#7501
                        "records": [],
                    }
                    for type_, subname in self._deletions
                ]
                + [
                    {
                        "name": RRset.construct_name(subname, self._domain_name),
                        "type": type_,
                        "ttl": RRset.objects.values_list("ttl", flat=True).get(
                            domain__name=self._domain_name,
                            type=type_,
                            subname=subname,
                        ),
                        "changetype": "REPLACE",
                        "records": [
                            {"content": rr.content, "disabled": False}
                            for rr in RR.objects.filter(
                                rrset__domain__name=self._domain_name,
                                rrset__type=type_,
                                rrset__subname=subname,
                            )
                        ],
                    }
                    for type_, subname in (self._additions | self._modifications)
                    - self._deletions
                ]
            }

            if data["rrsets"]:
                pdns.update_zone(self.domain_name, data)

        def __str__(self):
            return (
                "Update RRsets of %s: additions=%s, modifications=%s, deletions=%s"
                % (
                    self.domain_name,
                    list(self._additions),
                    list(self._modifications),
                    list(self._deletions),
                )
            )

    def _create_domain_change(self, domain_name, nslord):
        return PDNSChangeTracker.CreateDomain(domain_name)

    def _delete_domain_change(self, domain_name, nslord):
        return PDNSChangeTracker.DeleteDomain(domain_name)

    def _update_rrsets_change(
        self, domain_name, additions, modifications, deletions, nslord
    ):
        return PDNSChangeTracker.CreateUpdateDeleteRRSets(
            domain_name, additions, modifications, deletions
        )


class KnotChangeTracker(BaseChangeTracker):
    class KnotChange(BaseChangeTracker.Change):
        pass

    class CreateDomain(KnotChange):
        @property
        def axfr_required(self):
            return True

        def nslord_do(self):
            knot.create_zone(self.domain_name)
            knot.ensure_default_ns(self.domain_name)
            pdns.create_zone_master(
                self.domain_name, master_host=settings.NSLORD_KNOT_HOST
            )
            pdns.update_catalog(self.domain_name)

        def api_do(self):
            rr_set = RRset(
                domain=Domain.objects.get(name=self.domain_name),
                type="NS",
                subname="",
                ttl=settings.DEFAULT_NS_TTL,
            )
            rr_set.save()

            rrs = [RR(rrset=rr_set, content=ns) for ns in settings.DEFAULT_NS]
            RR.objects.bulk_create(rrs)  # One INSERT

        def pch_do(self):
            pch.create_domains([self.domain_name])

        def __str__(self):
            return "Create Domain %s" % self.domain_name

    class DeleteDomain(KnotChange):
        @property
        def axfr_required(self):
            return False

        def nslord_do(self):
            knot.delete_zone(self.domain_name)
            pdns.delete_zone_master(self.domain_name)
            pdns.update_catalog(self.domain_name, delete=True)

        def pch_do(self):
            pch.delete_domains([self.domain_name])

        def __str__(self):
            return "Delete Domain %s" % self.domain_name

    class CreateUpdateDeleteRRSets(KnotChange):
        def __init__(self, domain_name, additions, modifications, deletions):
            super().__init__(domain_name)
            self._additions = additions
            self._modifications = modifications
            self._deletions = deletions

        @property
        def axfr_required(self):
            return True

        def nslord_do(self):
            knot.update_rrsets(
                self.domain_name, self._additions, self._modifications, self._deletions
            )

        def __str__(self):
            return (
                "Update RRsets of %s: additions=%s, modifications=%s, deletions=%s"
                % (
                    self.domain_name,
                    list(self._additions),
                    list(self._modifications),
                    list(self._deletions),
                )
            )

    def _create_domain_change(self, domain_name, nslord):
        return KnotChangeTracker.CreateDomain(domain_name)

    def _delete_domain_change(self, domain_name, nslord):
        return KnotChangeTracker.DeleteDomain(domain_name)

    def _update_rrsets_change(
        self, domain_name, additions, modifications, deletions, nslord
    ):
        return KnotChangeTracker.CreateUpdateDeleteRRSets(
            domain_name, additions, modifications, deletions
        )


class NSLordChangeTracker(BaseChangeTracker):
    def _backend(self, nslord):
        if nslord == Domain.NSLord.KNOT:
            return KnotChangeTracker
        return PDNSChangeTracker

    def _create_domain_change(self, domain_name, nslord):
        return self._backend(nslord).CreateDomain(domain_name)

    def _delete_domain_change(self, domain_name, nslord):
        return self._backend(nslord).DeleteDomain(domain_name)

    def _update_rrsets_change(
        self, domain_name, additions, modifications, deletions, nslord
    ):
        return self._backend(nslord).CreateUpdateDeleteRRSets(
            domain_name, additions, modifications, deletions
        )
