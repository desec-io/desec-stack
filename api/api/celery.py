import logging
import pprint

import django.utils.log
from django.apps import apps as django_apps
from celery import Celery
from celery.signals import task_failure

app = Celery("api", include="desecapi.mail_backends")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


class CeleryFormatter(logging.Formatter):
    def format(self, record):
        return (
            f"Task: {record.sender}\n"
            f"Task arguments: {record.task_args}\n"
            f"Task keyword arguments: {record.task_kwargs}\n"
            f"Task ID: {record.task_id}\n"
            f"Exception Information:\n{pprint.pformat(record.exception.__dict__)}"
        )


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))


logger = logging.getLogger(__name__)


def _configure_logger():
    if getattr(_configure_logger, "configured", False):
        return
    if not django_apps.ready:
        return
    handler = django.utils.log.AdminEmailHandler()
    handler.setFormatter(CeleryFormatter())
    logger.addHandler(handler)
    _configure_logger.configured = True


@task_failure.connect()
def task_failure(task_id, exception, args, kwargs, traceback, einfo, **other_kwargs):
    _configure_logger()
    try:
        sender = other_kwargs.get("sender").name
    except AttributeError:
        sender = "<unknown sender in task_failure>"

    logger.error(
        "Celery %s in %s",
        type(exception).__name__,
        sender,
        extra={
            "request": None,
            "task_id": task_id,
            "exception": exception,
            "task_args": args,
            "task_kwargs": pprint.pformat(kwargs),
            "sender": sender,
        },
        exc_info=einfo,
    )


logger = logging.getLogger(__name__)
handler = django.utils.log.AdminEmailHandler()
handler.setFormatter(CeleryFormatter())
logger.addHandler(handler)
