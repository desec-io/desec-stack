import secrets
import socket

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.db.transaction import atomic
from django.utils import timezone

from desecapi import metrics, replication
from desecapi.models import RRset, RR, Domain
from desecapi.pdns import _pdns_post, NSLORD, NSMASTER, _pdns_delete, _pdns_patch, _pdns_put, pdns_id, \
    construct_catalog_rrset


class PDNSChangeTracker:
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

    class PDNSChange:
        """
        A reversible, atomic operation against the powerdns API.
        """

        def __init__(self, domain_name):
            self._domain_name = domain_name

        @property
        def domain_name(self):
            return self._domain_name

        @property
        def domain_name_normalized(self):
            return self._domain_name + '.'

        @property
        def domain_pdns_id(self):
            return pdns_id(self._domain_name)

        @property
        def axfr_required(self):
            raise NotImplementedError()

        def pdns_do(self):
            raise NotImplementedError()

        def api_do(self):
            raise NotImplementedError()

        def update_catalog(self, delete=False):
            content = _pdns_patch(NSMASTER, '/zones/' + pdns_id(settings.CATALOG_ZONE),
                               {'rrsets': [construct_catalog_rrset(zone=self.domain_name, delete=delete)]})
            metrics.get('desecapi_pdns_catalog_updated').inc()
            return content

    class CreateDomain(PDNSChange):
        @property
        def axfr_required(self):
            return True

        def pdns_do(self):
            salt = secrets.token_hex(nbytes=8)
            _pdns_post(
                NSLORD, '/zones?rrsets=false',
                {
                    'name': self.domain_name_normalized,
                    'kind': 'MASTER',
                    'dnssec': True,
                    'nsec3param': '1 0 127 %s' % salt,
                    'nameservers': settings.DEFAULT_NS,
                    'rrsets': [{
                        'name': self.domain_name_normalized,
                        'type': 'SOA',
                        # SOA RRset TTL: 300 (used as TTL for negative replies including NSEC3 records)
                        'ttl': 300,
                        'records': [{
                            # SOA refresh: 1 day (only needed for nslord --> nsmaster replication after RRSIG rotation)
                            # SOA retry = refresh
                            # SOA expire: 4 weeks (all signatures will have expired anyways)
                            # SOA minimum: 3600 (for CDS, CDNSKEY, DNSKEY, NSEC3PARAM)
                            'content': 'get.desec.io. get.desec.io. 1 86400 86400 2419200 3600',
                            'disabled': False
                        }],
                    }],
                }
            )

            _pdns_post(
                NSMASTER, '/zones?rrsets=false',
                {
                    'name': self.domain_name_normalized,
                    'kind': 'SLAVE',
                    'masters': [socket.gethostbyname('nslord')]
                }
            )

            self.update_catalog()

        def api_do(self):
            rr_set = RRset(
                domain=Domain.objects.get(name=self.domain_name),
                type='NS', subname='',
                ttl=settings.DEFAULT_NS_TTL,
            )
            rr_set.save()

            rrs = [RR(rrset=rr_set, content=ns) for ns in settings.DEFAULT_NS]
            RR.objects.bulk_create(rrs)  # One INSERT

        def __str__(self):
            return 'Create Domain %s' % self.domain_name

    class DeleteDomain(PDNSChange):
        @property
        def axfr_required(self):
            return False

        def pdns_do(self):
            _pdns_delete(NSLORD, '/zones/' + self.domain_pdns_id)
            _pdns_delete(NSMASTER, '/zones/' + self.domain_pdns_id)
            self.update_catalog(delete=True)

        def api_do(self):
            pass

        def __str__(self):
            return 'Delete Domain %s' % self.domain_name

    class CreateUpdateDeleteRRSets(PDNSChange):
        def __init__(self, domain_name, additions, modifications, deletions):
            super().__init__(domain_name)
            self._additions = additions
            self._modifications = modifications
            self._deletions = deletions

        @property
        def axfr_required(self):
            return True

        def pdns_do(self):
            data = {
                'rrsets':
                    [
                        {
                            'name': RRset.construct_name(subname, self._domain_name),
                            'type': type_,
                            'ttl': 1,  # some meaningless integer required by pdns's syntax
                            'changetype': 'REPLACE',  # don't use "DELETE" due to desec-stack#220, PowerDNS/pdns#7501
                            'records': []
                        }
                        for type_, subname in self._deletions
                    ] + [
                        {
                            'name': RRset.construct_name(subname, self._domain_name),
                            'type': type_,
                            'ttl': RRset.objects.values_list('ttl', flat=True).get(domain__name=self._domain_name,
                                                                                   type=type_, subname=subname),
                            'changetype': 'REPLACE',
                            'records': [
                                {'content': rr.content, 'disabled': False}
                                for rr in RR.objects.filter(
                                    rrset__domain__name=self._domain_name,
                                    rrset__type=type_,
                                    rrset__subname=subname)
                            ]
                        }
                        for type_, subname in (self._additions | self._modifications) - self._deletions
                    ]
            }

            if data['rrsets']:
                _pdns_patch(NSLORD, '/zones/' + self.domain_pdns_id, data)

        def api_do(self):
            pass

        def __str__(self):
            return 'Update RRsets of %s: additions=%s, modifications=%s, deletions=%s' % \
                   (self.domain_name, list(self._additions), list(self._modifications), list(self._deletions))

    def __init__(self):
        self._domain_additions = set()
        self._domain_deletions = set()
        self._rr_set_additions = {}
        self._rr_set_modifications = {}
        self._rr_set_deletions = {}
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
        PDNSChangeTracker._active_change_trackers += 1
        assert PDNSChangeTracker._active_change_trackers == 1, 'Nesting %s is not supported.' % self.__class__.__name__
        self._domain_additions = set()
        self._domain_deletions = set()
        self._rr_set_additions = {}
        self._rr_set_modifications = {}
        self._rr_set_deletions = {}
        self._manage_signals('connect')
        self.transaction = atomic()
        self.transaction.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        PDNSChangeTracker._active_change_trackers -= 1
        self._manage_signals('disconnect')

        if exc_type:
            # An exception occurred inside our context, exit db transaction and dismiss pdns changes
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            return

        # TODO introduce two phase commit protocol
        changes = self._compute_changes()
        axfr_required = set()
        replication_required = set()
        for change in changes:
            try:
                change.pdns_do()
                change.api_do()
                replication_required.add(change.domain_name)
                if change.axfr_required:
                    axfr_required.add(change.domain_name)
            except Exception as e:
                self.transaction.__exit__(type(e), e, e.__traceback__)
                exc = ValueError(f'For changes {list(map(str, changes))}, {type(e)} occurred during {change}: {str(e)}')
                raise exc from e

        self.transaction.__exit__(None, None, None)

        for name in replication_required:
            replication.update.delay(name)
        for name in axfr_required:
            _pdns_put(NSMASTER, '/zones/%s/axfr-retrieve' % pdns_id(name))
        Domain.objects.filter(name__in=axfr_required).update(published=timezone.now())

    def _compute_changes(self):
        changes = []

        for domain_name in self._domain_deletions:
            # discard any RR set modifications
            self._rr_set_additions.pop(domain_name, None)
            self._rr_set_modifications.pop(domain_name, None)
            self._rr_set_deletions.pop(domain_name, None)

            changes.append(PDNSChangeTracker.DeleteDomain(domain_name))

        for domain_name in self._rr_set_additions.keys() | self._domain_additions:
            if domain_name in self._domain_additions:
                changes.append(PDNSChangeTracker.CreateDomain(domain_name))

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

            # We send RR sets to PDNS if one of the following conditions holds:
            # (a) RR set was added and has at least one RR
            # (b) RR set was modified
            # (c) RR set was deleted

            # Conditions (b) and (c) are already covered in the modifications and deletions list,
            # we filter the additions list to remove newly-added, but empty RR sets
            additions -= {
                (type_, subname) for (type_, subname) in additions
                if not RR.objects.filter(
                    rrset__domain__name=domain_name,
                    rrset__type=type_,
                    rrset__subname=subname).exists()
            }

            if additions | modifications | deletions:
                changes.append(PDNSChangeTracker.CreateUpdateDeleteRRSets(
                    domain_name, additions, modifications, deletions))

        return changes

    def _rr_set_updated(self, rr_set: RRset, deleted=False, created=False):
        if self._rr_set_modifications.get(rr_set.domain.name, None) is None:
            self._rr_set_additions[rr_set.domain.name] = set()
            self._rr_set_modifications[rr_set.domain.name] = set()
            self._rr_set_deletions[rr_set.domain.name] = set()

        additions = self._rr_set_additions[rr_set.domain.name]
        modifications = self._rr_set_modifications[rr_set.domain.name]
        deletions = self._rr_set_deletions[rr_set.domain.name]

        item = (rr_set.type, rr_set.subname)
        if created:
            additions.add(item)
            assert item not in modifications
            deletions.discard(item)
        elif deleted:
            if item in additions:
                additions.remove(item)
                modifications.discard(item)
                # no change to deletions
            else:
                # item not in additions
                modifications.discard(item)
                deletions.add(item)
        elif not created and not deleted:
            # we don't care if item was created or not
            modifications.add(item)
            assert item not in deletions
        else:
            raise ValueError('An RR set cannot be created and deleted at the same time.')

    def _domain_updated(self, domain: Domain, created=False, deleted=False):
        if not created and not deleted:
            # NOTE that the name must not be changed by API contract with models, hence here no-op for pdns.
            return

        name = domain.name
        additions = self._domain_additions
        deletions = self._domain_deletions

        if created and deleted:
            raise ValueError('A domain set cannot be created and deleted at the same time.')

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
    def _on_rr_post_save(self, signal, sender, instance: RR, created, update_fields, raw, using, **kwargs):
        self._rr_set_updated(instance.rrset)

    # noinspection PyUnusedLocal
    def _on_rr_post_delete(self, signal, sender, instance: RR, using, **kwargs):
        self._rr_set_updated(instance.rrset)

    # noinspection PyUnusedLocal
    def _on_rr_set_post_save(self, signal, sender, instance: RRset, created, update_fields, raw, using, **kwargs):
        self._rr_set_updated(instance, created=created)

    # noinspection PyUnusedLocal
    def _on_rr_set_post_delete(self, signal, sender, instance: RRset, using, **kwargs):
        self._rr_set_updated(instance, deleted=True)

    # noinspection PyUnusedLocal
    def _on_domain_post_save(self, signal, sender, instance: Domain, created, update_fields, raw, using, **kwargs):
        self._domain_updated(instance, created=created)

    # noinspection PyUnusedLocal
    def _on_domain_post_delete(self, signal, sender, instance: Domain, using, **kwargs):
        self._domain_updated(instance, deleted=True)

    def __str__(self):
        all_rr_sets = self._rr_set_additions.keys() | self._rr_set_modifications.keys() | self._rr_set_deletions.keys()
        all_domains = self._domain_additions | self._domain_deletions
        return '<%s: %i added or deleted domains; %i added, modified or deleted RR sets>' % (
            self.__class__.__name__,
            len(all_domains),
            len(all_rr_sets)
        )
