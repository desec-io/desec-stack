from django.db.models.signals import post_save, post_delete
from django.db.transaction import atomic
from django.utils import timezone

import desecapi.pdns as pdns
from desecapi import replication
from desecapi.models import RRset, RR, Domain


class PDNSChangeTracker:
    """
    Hooks up to model signals to maintain three sets:

    - `additions`: set of added domains
    - `modifications`: set of modified domains, i.e. domains for which RRs or RRsets have been changed
    - `deletions`: set of deleted domains

    The addition and deletion sets are guaranteed to be disjoint.

    Note every change tracker object will track all changes to the model across threading.
    To avoid side-effects, it is recommended that in each Django process, only one change
    tracker is run at a time, i.e. do not use them in parallel (e.g., in a multi-threading
    scenario), do not use them nested.
    """

    _active_change_trackers = 0

    def __init__(self):
        self._additions = set()
        self._modifications = set()
        self._deletions = set()
        self.transaction = None

    @classmethod
    def track(cls, f):
        """
        Execute function f with the change tracker.
        :param f: Function to be tracked for PDNS-relevant changes.
        :return: Returns the return value of f.
        """
        with cls():
            return f()

    def _manage_signals(self, method):
        if method not in ['connect', 'disconnect']:
            raise ValueError()
        getattr(post_save, method)(self._on_rr_post_save, sender=RR, dispatch_uid=self.__module__)
        getattr(post_delete, method)(self._on_rr_post_delete, sender=RR, dispatch_uid=self.__module__)
        getattr(post_save, method)(self._on_rr_set_post_save, sender=RRset, dispatch_uid=self.__module__)
        getattr(post_delete, method)(self._on_rr_set_post_delete, sender=RRset, dispatch_uid=self.__module__)
        getattr(post_save, method)(self._on_domain_post_save, sender=Domain, dispatch_uid=self.__module__)
        getattr(post_delete, method)(self._on_domain_post_delete, sender=Domain, dispatch_uid=self.__module__)

    def __enter__(self):
        # TODO maybe nesting/parallel execution isn't a problem anymore?
        PDNSChangeTracker._active_change_trackers += 1
        assert PDNSChangeTracker._active_change_trackers == 1, 'Nesting %s is not supported.' % self.__class__.__name__
        self._additions = set()
        self._modifications = set()
        self._deletions = set()
        self._manage_signals('connect')
        self.transaction = atomic()
        self.transaction.__enter__()  # TODO move transaction out of change tracker

    def __exit__(self, exc_type, exc_val, exc_tb):
        PDNSChangeTracker._active_change_trackers -= 1
        self._manage_signals('disconnect')

        if exc_type:
            # An exception occurred inside our context, exit db transaction and dismiss pdns changes
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            return False  # https://stackoverflow.com/a/15344080
        else:
            self.transaction.__exit__(None, None, None)

        # Increase serial
        for name in self._modifications:
            Domain.objects.get(name=name).increase_serial()

        # Create zones at nsmaster
        for name in self._additions:
            pdns.create_cryptokey(name)
            pdns.create_zone(name)
            pdns.catalog_add(name)

        # Delete zones from nsmaster
        for name in self._deletions:
            pdns.delete_zone(name)
            pdns.catalog_remove(name)

        # trigger zone file updates
        for name in self._additions | self._modifications | self._deletions:
            replication.update.delay(name)

        # trigger AXFRs
        axfr_required = self._additions | self._modifications - self._deletions
        for name in axfr_required:
            pdns.trigger_axfr(name)

        # log publish date
        Domain.objects.filter(name__in=axfr_required).update(published=timezone.now())

    # noinspection PyUnusedLocal
    def _on_rr_post_save(self, signal, sender, instance: RR, created, update_fields, raw, using, **kwargs):
        self._modifications.add(instance.rrset.domain.name)

    # noinspection PyUnusedLocal
    def _on_rr_post_delete(self, signal, sender, instance: RR, using, **kwargs):
        self._modifications.add(instance.rrset.domain.name)

    # noinspection PyUnusedLocal
    def _on_rr_set_post_save(self, signal, sender, instance: RRset, created, update_fields, raw, using, **kwargs):
        self._modifications.add(instance.domain.name)

    # noinspection PyUnusedLocal
    def _on_rr_set_post_delete(self, signal, sender, instance: RRset, using, **kwargs):
        self._modifications.add(instance.domain.name)

    # noinspection PyUnusedLocal
    def _on_domain_post_save(self, signal, sender, instance: Domain, created, update_fields, raw, using, **kwargs):
        if created:
            if instance.name not in self._deletions:
                # schedule for creation if this domain wasn't scheduled for deletion
                self._additions.add(instance.name)
            else:
                # schedule for modification as this domain was scheduled to be deleted before
                self._modifications.add(instance.name)
            # don't delete this domain anymore
            self._deletions -= {instance.name}

    # noinspection PyUnusedLocal
    def _on_domain_post_delete(self, signal, sender, instance: Domain, using, **kwargs):
        if instance.name not in self._additions:
            # only schedule for deletion if this domain wasn't scheduled for creation
            self._deletions.add(instance.name)
        # don't add this domain anymore
        self._additions -= {instance.name}
        self._modifications -= {instance.name}

    def __str__(self):
        return f"<{self.__class__.__name__}: " \
               f"added {len(self._additions)}, " \
               f"modified {len(self._modifications)}, " \
               f"deleted {len(self._deletions)} domains>"
