import random
import socket

from django.db.models.signals import post_save, post_delete
from django.db.transaction import atomic
from django.utils import timezone

from api import settings as api_settings
from desecapi.models import RRset, RR, Domain
from desecapi.pdns import _pdns_post, NSLORD, NSMASTER, _pdns_delete, _pdns_patch, _pdns_put, pdns_id


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
    """

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

    class CreateDomain(PDNSChange):
        @property
        def axfr_required(self):
            return True

        def pdns_do(self):
            salt = '%016x' % random.randrange(16 ** 16)
            _pdns_post(
                NSLORD, '/zones',
                {
                    'name': self.domain_name_normalized,
                    'kind': 'MASTER',
                    'dnssec': True,
                    'nsec3param': '1 0 127 %s' % salt,
                    'nameservers': api_settings.DEFAULT_NS
                }
            )

            _pdns_post(
                NSMASTER, '/zones',
                {
                    'name': self.domain_name_normalized,
                    'kind': 'SLAVE',
                    'masters': [socket.gethostbyname('nslord')]
                }
            )

        def api_do(self):
            rr_set = RRset(
                domain=Domain.objects.get(name=self.domain_name),
                type='NS', subname='',
                ttl=api_settings.DEFAULT_NS_TTL,
            )
            rr_set.save()

            rrs = [RR(rrset=rr_set, content=ns) for ns in api_settings.DEFAULT_NS]
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
                    ] + [
                        {
                            'name': RRset.construct_name(subname, self._domain_name),
                            'type': type_,
                            'changetype': 'DELETE',
                            'records': []
                        }
                        for type_, subname in self._deletions
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

    def _manage_signals(self, method):
        if method not in ['connect', 'disconnect']:
            raise ValueError()
        getattr(post_save, method)(self._on_rr_post_save, sender=RR)
        getattr(post_delete, method)(self._on_rr_post_delete, sender=RR)
        getattr(post_save, method)(self._on_rr_set_post_save, sender=RRset)
        getattr(post_delete, method)(self._on_rr_set_post_delete, sender=RRset)
        getattr(post_save, method)(self._on_domain_post_save, sender=Domain)
        getattr(post_delete, method)(self._on_domain_post_delete, sender=Domain)

    def __enter__(self):
        self._domain_additions = set()
        self._domain_deletions = set()
        self._rr_set_additions = {}
        self._rr_set_modifications = {}
        self._rr_set_deletions = {}
        self._manage_signals('connect')
        self.transaction = atomic()
        self.transaction.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._manage_signals('disconnect')

        if exc_type:
            # An exception occurred inside our context, exit db transaction and dismiss pdns changes
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            return

        # TODO introduce two phase commit protocol
        changes = self._compute_changes()
        axfr_required = set()
        for change in changes:
            try:
                change.pdns_do()
                change.api_do()
                if change.axfr_required:
                    axfr_required.add(change.domain_name)
            except RRset.DoesNotExist as e:
                self.transaction.__exit__(type(e), e, e.__traceback__)
                raise ValueError('For changes %s, could not find RRset when applying %s' %
                                 (list(map(str, changes)), change))
            except Exception as e:
                # TODO gather as much info as possible
                #  see if pdns and api are possibly in an inconsistent state
                self.transaction.__exit__(type(e), e, e.__traceback__)
                raise e

        self.transaction.__exit__(None, None, None)

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
