from django.core.management import BaseCommand
from desecapi.models import User
from desecapi import settings
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        users = User.objects.filter(created__lt=timezone.now()-timedelta(hours=settings.ABUSE_LOCK_ACCOUNT_BY_REGISTRATION_IP_PERIOD_HRS))
        for u in users:
            u.registration_remote_ip = ''
            u.save() # TODO bulk update?
