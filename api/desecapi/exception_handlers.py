import logging

from django.db.utils import OperationalError
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

    def _500():
        _log()

        # Let clients know that there is a problem
        response = Response({'detail': 'Internal Server Error. We\'re on it!'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return response

    def _503():
        _log()

        # Let clients know that there is a temporary problem
        response = Response({'detail': 'Please try again later.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return response

    # Catch DB exception and log an extra error for additional context
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
        metrics.get('desecapi_database_unavailable').inc()
        return _503()

    # OSError happens on system-related errors, like full disk or getaddrinfo() failure.
    if isinstance(exc, OSError):
        # TODO add metrics
        return _500()

    # The PSL encountered an unsupported rule
    if isinstance(exc, UnsupportedRule):
        # TODO add metrics
        return _500()

    # nslord/nsmaster returned an error
    if isinstance(exc, PDNSException):
        # TODO add metrics
        return _500()

    return drf_exception_handler(exc, context)
