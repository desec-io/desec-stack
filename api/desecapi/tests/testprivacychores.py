from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from desecapi.models import User
from desecapi.tests.base import DesecTestCase
from api import settings


class PrivacyChoresCommandTest(DesecTestCase):

    def test_delete_registration_ip(self):
        name1 = self.random_username()
        name2 = self.random_username()

        User(
            email=name1,
            registration_remote_ip='1.3.3.7',
        ).save()
        User(
            email=name2,
            registration_remote_ip='1.3.3.8',
        ).save()
        user2 = User.objects.get(email=name2)
        user2.created = timezone.now()-timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS+1)
        user2.save()

        user_count = User.objects.all().count()

        call_command('privacy-chores')

        self.assertEqual(User.objects.all().count(), user_count)
        self.assertEqual(User.objects.get(email=name1).registration_remote_ip, '1.3.3.7')
        self.assertEqual(User.objects.get(email=name2).registration_remote_ip, '')
