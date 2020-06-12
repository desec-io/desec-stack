import time

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from desecapi import models, serializers
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):

    @staticmethod
    def delete_expired_captchas():
        models.Captcha.objects.filter(created__lt=timezone.now() - settings.CAPTCHA_VALIDITY_PERIOD).delete()

    @staticmethod
    def delete_never_activated_users():
        # delete inactive users whose activation link expired and who never logged in
        # (this will not delete users who have used their account and were later disabled)
        models.User.objects.filter(is_active=False, last_login__exact=None,
                            created__lt=timezone.now() - settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE).delete()

    @staticmethod
    def update_healthcheck_timestamp():
        name = 'internal-timestamp.desec.test'
        try:
            domain = models.Domain.objects.get(name=name)
        except models.Domain.DoesNotExist:
            # Fail silently. If external alerting is configured, it will catch the problem; otherwise, we don't need it.
            print(f'{name} zone is not configured; skipping TXT record update')
            return

        instances = domain.rrset_set.filter(subname='', type='TXT').all()
        timestamp = int(time.time())
        content = f'"{timestamp}"'
        data = [{
            'subname': '',
            'type': 'TXT',
            'ttl': '3600',
            'records': [content]
        }]
        serializer = serializers.RRsetSerializer(instances, domain=domain, data=data, many=True, partial=True)
        serializer.is_valid(raise_exception=True)
        with PDNSChangeTracker():
            serializer.save()
        print(f'TXT {name} updated to {content}')

    def handle(self, *args, **kwargs):
        self.delete_expired_captchas()
        self.delete_never_activated_users()
        self.update_healthcheck_timestamp()
