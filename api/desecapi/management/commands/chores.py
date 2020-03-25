from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from desecapi.models import Captcha, User


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # delete expired captchas
        Captcha.objects.filter(created__lt=timezone.now() - settings.CAPTCHA_VALIDITY_PERIOD).delete()

        # delete inactive users whose activation link expired and who never logged in
        # (this will not delete users who have used their account and were later disabled)
        User.objects.filter(is_active=False, last_login__exact=None,
                            created__lt=timezone.now() - settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE).delete()
