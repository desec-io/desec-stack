from unittest import mock

from django.conf import settings
from django.core import management
from django.test import override_settings, TestCase
from django.utils import timezone

from desecapi.models import Captcha


class ChoresCommandTest(TestCase):
    @override_settings(CAPTCHA_VALIDITY_PERIOD=timezone.timedelta(hours=1))
    def test_captcha_cleanup(self):
        faketime = timezone.now() - settings.CAPTCHA_VALIDITY_PERIOD - timezone.timedelta(seconds=1)
        with mock.patch('django.db.models.fields.timezone.now', return_value=faketime):
            captcha1 = Captcha.objects.create()

        captcha2 = Captcha.objects.create()
        self.assertGreaterEqual((captcha2.created - captcha1.created).total_seconds(), 3601)

        management.call_command('chores')
        self.assertEqual(list(Captcha.objects.all()), [captcha2])
