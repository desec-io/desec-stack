import logging

from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from desecapi import metrics
from desecapi.exceptions import PDNSException


def exception_handler(exc, context):
    """
    desecapi specific exception handling. If no special treatment is applied,
    we default to restframework's exception handling. See also
    https://www.django-rest-framework.org/api-guide/exceptions/#custom-exception-handling
    """
    class_path = f"{exc.__class__.__module__}.{exc.__class__.__name__}"

    def _log():
        logger = logging.getLogger("django.request")
        logger.error(
            f"{class_path} Supplementary Information",
            exc_info=exc,
            stack_info=False,
        )

    def _409():
        return Response({"detail": f"Conflict: {exc}"}, status=status.HTTP_409_CONFLICT)

    def _500():
        _log()
        return Response(
            {"detail": "Internal Server Error. We're on it!"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    handlers = {
        IntegrityError: _409,
        OSError: _500,  # OSError happens on system-related errors, like full disk or getaddrinfo() failure.
        PDNSException: _500,  # nslord/nsmaster returned an error
    }

    for exception_class, handler in handlers.items():
        if isinstance(exc, exception_class):
            metrics.get("desecapi_exception").labels(class_path).inc()
            return handler()

    return drf_exception_handler(exc, context)
