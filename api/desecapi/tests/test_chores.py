from unittest import mock

from django.conf import settings
from django.core import management
from django.test import override_settings, TestCase
from django.utils import timezone

from desecapi.models import Captcha, User


class ChoresCommandTest(TestCase):
    @override_settings(CAPTCHA_VALIDITY_PERIOD=timezone.timedelta(hours=1))
    def test_captcha_cleanup(self):
        faketime = (
            timezone.now()
            - settings.CAPTCHA_VALIDITY_PERIOD
            - timezone.timedelta(seconds=1)
        )
        with mock.patch("django.db.models.fields.timezone.now", return_value=faketime):
            captcha1 = Captcha.objects.create()

        captcha2 = Captcha.objects.create()
        self.assertGreaterEqual(
            (captcha2.created - captcha1.created).total_seconds(), 3601
        )

        management.call_command("chores")
        self.assertEqual(list(Captcha.objects.all()), [captcha2])

    @override_settings(
        VALIDITY_PERIOD_VERIFICATION_SIGNATURE=timezone.timedelta(hours=1)
    )
    def test_inactive_user_cleanup(self):
        def create_users(kind):
            logintime = timezone.now() + timezone.timedelta(seconds=5)
            kwargs_list = [
                dict(
                    email=f"user1+{kind}@example.com", is_active=None, last_login=None
                ),
                dict(
                    email=f"user2+{kind}@example.com",
                    is_active=None,
                    last_login=logintime,
                ),
                dict(
                    email=f"user3+{kind}@example.com", is_active=False, last_login=None
                ),
                dict(
                    email=f"user4+{kind}@example.com",
                    is_active=False,
                    last_login=logintime,
                ),
                dict(
                    email=f"user5+{kind}@example.com", is_active=True, last_login=None
                ),
                dict(
                    email=f"user6+{kind}@example.com",
                    is_active=True,
                    last_login=logintime,
                ),
            ]
            return (User.objects.create(**kwargs) for kwargs in kwargs_list)

        # Old users
        faketime = (
            timezone.now()
            - settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE
            - timezone.timedelta(seconds=1)
        )
        with mock.patch("django.db.models.fields.timezone.now", return_value=faketime):
            expired_user, *_ = create_users("old")

        # New users
        create_users("new")

        all_users = set(User.objects.all())

        management.call_command("chores")
        # Check that only the expired user was deleted
        self.assertEqual(all_users - set(User.objects.all()), {expired_user})
