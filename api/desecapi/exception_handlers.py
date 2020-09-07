import logging

from django.db.utils import IntegrityError, OperationalError
from psl_dns.exceptions import UnsupportedRule
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

    def _log():
        logger = logging.getLogger('django.request')
        logger.error('{} Supplementary Information'.format(exc.__class__),
                     exc_info=exc, stack_info=False)

    def _409():
        return Response({'detail': f'Conflict: {exc}'}, status=status.HTTP_409_CONFLICT)

    def _500():
        return Response({'detail': "Internal Server Error. We're on it!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _503():
        return Response({'detail': 'Please try again later.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Catch DB OperationalError and log an extra error for additional context
    if (
        isinstance(exc, OperationalError) and
        isinstance(exc.args, (list, dict, tuple)) and
        exc.args and
        exc.args[0] in (
            2002,  # Connection refused (Socket)
            2003,  # Connection refused (TCP)
            2005,  # Unresolved host name
            2007,  # Server protocol mismatch
            2009,  # Wrong host info
            2026,  # SSL connection error
        )
    ):
        _log()
        metrics.get('desecapi_database_unavailable').inc()
        return _503()

    handlers = {
        IntegrityError: _409,
        OSError: _500,  # OSError happens on system-related errors, like full disk or getaddrinfo() failure.
        UnsupportedRule: _500,  # The PSL encountered an unsupported rule
        PDNSException: _500,  # nslord/nsmaster returned an error
    }

    for exception_class, handler in handlers.items():
        if isinstance(exc, exception_class):
            _log()
            # TODO add metrics
            return handler()

    return drf_exception_handler(exc, context)
