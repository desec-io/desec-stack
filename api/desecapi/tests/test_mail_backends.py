from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMessage, get_connection
from django.test import TestCase

from desecapi import mail_backends


@mock.patch.dict(mail_backends.TASKS,
                 {key: type('obj', (object,), {'delay': mail_backends.MultiLaneEmailBackend._run_task})
                  for key in mail_backends.TASKS})
class MultiLaneEmailBackendTestCase(TestCase):
    test_backend = settings.EMAIL_BACKEND

    def test_lanes(self):
        debug_params = {'foo': 'bar'}
        debug_params_orig = debug_params.copy()

        with self.settings(EMAIL_BACKEND='desecapi.mail_backends.MultiLaneEmailBackend'):
            for lane in ['email_slow_lane', 'email_fast_lane', None]:
                subject = f'Test subject for lane {lane}'
                connection = get_connection(lane=lane, backbackend=self.test_backend, debug=debug_params)
                EmailMessage(subject=subject, to=['to@test.invalid'], connection=connection).send()
                self.assertEqual(mail.outbox[-1].connection.task_kwargs['debug'],
                                 {'lane': lane or 'email_slow_lane', **debug_params})
                self.assertEqual(mail.outbox[-1].subject, subject)

        # Check that the backend hasn't modified the dict we passed
        self.assertEqual(debug_params, debug_params_orig)
