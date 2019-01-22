from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from desecapi.models import User, MyUserManager
from .utils import utils
from api import settings
from datetime import timedelta


class PrivacyChoresCommandTest(TestCase):

    def test_delete_registration_ip_for_old_users(self):
        name1 = utils.generateUsername()
        name2 = utils.generateUsername()

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
