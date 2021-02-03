import datetime

from django.conf import settings
from django.core.mail import get_connection, mail_admins
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import F, Max, OuterRef, Subquery
from django.db.models.functions import Greatest
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.reverse import reverse

from desecapi import models, serializers, views
from desecapi.pdns_change_tracker import PDNSChangeTracker


fresh_days = 183
notice_days_notify = 28
notice_days_warn = 7


class Command(BaseCommand):
    base_queryset = models.Domain.objects.exclude(renewal_state=models.Domain.RenewalState.IMMORTAL)
    _rrsets_outer_queryset = models.RRset.objects.filter(domain=OuterRef('pk')).values('domain')  # values() is GROUP BY
    _max_touched = Subquery(_rrsets_outer_queryset.annotate(max_touched=Max('touched')).values('max_touched'))

    @classmethod
    def renew_touched_domains(cls):
        recently_active_domains = cls.base_queryset.annotate(
            last_active=Greatest(cls._max_touched, 'published')
        ).filter(
            last_active__date__gte=timezone.localdate() - datetime.timedelta(days=183),
            renewal_changed__lt=F('last_active'),
        )

        print('Renewing domains:', *recently_active_domains.values_list('name', flat=True))
        recently_active_domains.update(renewal_state=models.Domain.RenewalState.FRESH, renewal_changed=F('last_active'))

    @classmethod
    def warn_domain_deletion(cls, renewal_state, notice_days, inactive_days):
        def confirmation_link(domain_name, user):
            action = models.AuthenticatedRenewDomainBasicUserAction(domain=domain_name, user=user)
            verification_code = serializers.AuthenticatedRenewDomainBasicUserActionSerializer(action).data['code']
            request = RequestFactory().generic('', '', secure=True, HTTP_HOST=f'desec.{settings.DESECSTACK_DOMAIN}')
            return reverse('v1:confirm-renew-domain', request=request, args=[verification_code])

        # We act when `renewal_changed` is at least this date (or older)
        inactive_threshold = timezone.localdate() - datetime.timedelta(days=inactive_days)
        # Filter candidates which have the state of interest, at least since the calculated date
        expiry_candidates = cls.base_queryset.filter(renewal_state=renewal_state,
                                                     renewal_changed__date__lte=inactive_threshold)

        # Group domains by user, so that we can send one message per user
        domain_user_map = {}
        for domain in expiry_candidates.order_by('name'):
            if domain.owner not in domain_user_map:
                domain_user_map[domain.owner] = []
            domain_user_map[domain.owner].append(domain)

        # Prepare and send emails, and keep renewal status in sync
        deletion_date = timezone.localdate() + datetime.timedelta(days=notice_days)
        for user, domains in domain_user_map.items():
            with transaction.atomic():
                # Update renewal status of the user's affected domains, but don't commit before sending the email
                for domain in domains:
                    domain.renewal_state += 1
                    domain.renewal_changed = timezone.now()
                    domain.save(update_fields=['renewal_state', 'renewal_changed'])
                links = [{'name': domain, 'confirmation_link': confirmation_link(domain, user)} for domain in domains]
                user.send_email('renew-domain', context={'domains': links, 'deletion_date': deletion_date})

    @classmethod
    def delete_domains(cls, inactive_days):
        expired_domains = cls.base_queryset.filter(renewal_state=models.Domain.RenewalState.WARNED).annotate(
            last_active=Greatest(cls._max_touched, 'published')
        ).filter(
            renewal_changed__date__lte=timezone.localdate() - datetime.timedelta(days=notice_days_warn),
            last_active__date__lte=timezone.localdate() - datetime.timedelta(days=inactive_days),
        )

        for domain in expired_domains:
            with PDNSChangeTracker():
                domain.delete()
            if not domain.owner.domains.exists():
                domain.owner.delete()
        # Do one large delegation update
        with PDNSChangeTracker():
            for domain in expired_domains:
                views.DomainViewSet.auto_delegate(domain)

    def handle(self, *args, **kwargs):
        try:
            # Reset renewal status for domains that have recently been touched
            self.renew_touched_domains()

            # Announce domain deletion in `notice_days_notice` days if not yet notified (FRESH) and inactive for
            # `inactive_days` days. Updates status from FRESH to NOTIFIED.
            self.warn_domain_deletion(models.Domain.RenewalState.FRESH, notice_days_notify, fresh_days)

            # After `notice_days_notify - notice_days_warn` more days, warn again if the status has not changed
            # Updates status from NOTIFIED to WARNED.
            self.warn_domain_deletion(models.Domain.RenewalState.NOTIFIED, notice_days_warn,
                                      notice_days_notify - notice_days_warn)

            # Finally, delete domains inactive for `inactive_days + notice_days_notify` days if status has not changed
            self.delete_domains(fresh_days + notice_days_notify)
        except Exception as e:
            subject = 'Renewal Exception!'
            message = f'{type(e)}\n\n{str(e)}'
            print(f'Chores exception: {type(e)}, {str(e)}')
            mail_admins(subject, message, connection=get_connection('django.core.mail.backends.smtp.EmailBackend'))
