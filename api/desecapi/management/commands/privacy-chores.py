from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from desecapi.models import User


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        users = User.objects.filter(created__lt=timezone.now()-timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS))
        users.update(registration_remote_ip='')
