from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from desecapi import models


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

    def handle(self, *args, **kwargs):
        self.delete_expired_captchas()
        self.delete_never_activated_users()
