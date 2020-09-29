import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from djcelery_email.utils import dict_to_email, email_to_dict

from desecapi import metrics


logger = logging.getLogger(__name__)


class MultiLaneEmailBackend(BaseEmailBackend):
    config = {'ignore_result': True}
    default_backend = 'django.core.mail.backends.smtp.EmailBackend'

    def __init__(self, lane: str = None, fail_silently=False, **kwargs):
        lane = lane or next(iter(settings.TASK_CONFIG))
        self.config.update(name=lane, queue=lane)
        self.config.update(settings.TASK_CONFIG[lane])
        self.task_kwargs = kwargs.copy()
        # Make a copy to ensure we don't modify input dict when we set the 'lane'
        self.task_kwargs['debug'] = self.task_kwargs.pop('debug', {}).copy()
        self.task_kwargs['debug']['lane'] = lane
        super().__init__(fail_silently)

    def send_messages(self, email_messages):
        dict_messages = [email_to_dict(msg) for msg in email_messages]
        TASKS[self.config['name']].delay(dict_messages, **self.task_kwargs)
        return len(email_messages)

    @staticmethod
    def _run_task(messages, debug, **kwargs):
        logger.warning('Sending queued email, details: %s', debug)
        kwargs.setdefault('backend', kwargs.pop('backbackend', MultiLaneEmailBackend.default_backend))
        with get_connection(**kwargs) as connection:
            return connection.send_messages([dict_to_email(message) for message in messages])
        
    @property
    def task(self):
        return shared_task(**self.config)(self._run_task)


# Define tasks so that Celery can discovery them
TASKS = {
    name: MultiLaneEmailBackend(lane=name, fail_silently=True).task
    for name in settings.TASK_CONFIG
    if name.startswith('email_')
}
