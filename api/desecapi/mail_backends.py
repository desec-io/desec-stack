import copy
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.mail.backends.base import BaseEmailBackend

from desecapi import metrics


logger = logging.getLogger(__name__)


def serialize(message: EmailMessage) -> dict:
    """
    Represents an EmailMessage by its attributes, so that it can be passed through the
    task queue. Attachment contents must be str (we don't send binary attachments).
    """
    return {
        key: value
        for key, value in message.__dict__.items()
        if key not in settings.EMAIL_MESSAGE_TRANSIENT_ATTRIBUTES
    }


def deserialize(attributes: dict) -> EmailMessage:
    """Inverse of serialize()."""
    message = EmailMessage()
    message.__dict__.update(copy.deepcopy(attributes))  # copy: retries reuse the input
    return message


class MultiLaneEmailBackend(BaseEmailBackend):
    config = {"ignore_result": True}
    default_backend = "django.core.mail.backends.smtp.EmailBackend"

    def __init__(self, lane: str = None, fail_silently=False, **kwargs):
        lane = lane or next(iter(settings.TASK_CONFIG))
        self.config.update(name=lane, queue=lane)
        self.config.update(settings.TASK_CONFIG[lane])
        self.task_kwargs = kwargs.copy()
        # Make a copy to ensure we don't modify input dict when we set the 'lane'
        self.task_kwargs["debug"] = self.task_kwargs.pop("debug", {}).copy()
        self.task_kwargs["debug"]["lane"] = lane
        super().__init__(fail_silently)

    def send_messages(self, email_messages):
        messages = [serialize(message) for message in email_messages]
        TASKS[self.config["name"]].delay(messages, **self.task_kwargs)
        return len(email_messages)

    @staticmethod
    def _run_task(messages, debug, **kwargs):
        logger.warning("Sending queued email, details: %s", debug)
        kwargs.setdefault(
            "backend", kwargs.pop("backbackend", MultiLaneEmailBackend.default_backend)
        )
        with get_connection(**kwargs) as connection:
            return connection.send_messages(
                [deserialize(message) for message in messages]
            )

    @property
    def task(self):
        return shared_task(**self.config)(self._run_task)


# Define tasks so that Celery can discovery them
TASKS = {
    name: MultiLaneEmailBackend(lane=name, fail_silently=True).task
    for name in settings.TASK_CONFIG
    if name.startswith("email_")
}
