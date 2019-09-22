from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from desecapi.models import Captcha


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # delete expired captchas
        Captcha.objects.filter(created__lt=timezone.now() - settings.CAPTCHA_VALIDITY_PERIOD).delete()
