import logging

from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from psl_dns.exceptions import UnsupportedRule


def exception_handler(exc, context):
    """
    desecapi specific exception handling. If no special treatment is applied,
    we default to restframework's exception handling. See also
    https://www.django-rest-framework.org/api-guide/exceptions/#custom-exception-handling
    """

    def _perform_handling(name):
        logger = logging.getLogger('django.request')
        logger.error('{} Supplementary Information'.format(name),
                     exc_info=exc, stack_info=False)

        # Gracefully let clients know that we cannot connect to the database
        return Response({'detail': 'Please try again later.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Catch DB exception and log an extra error for additional context
    if isinstance(exc, OperationalError):
        if isinstance(exc.args, (list, dict, tuple)) and exc.args and \
            exc.args[0] in (
                1040,  # Too many connections
                2002,  # Connection refused (Socket)
                2003,  # Connection refused (TCP)
                2005,  # Unresolved host name
                2007,  # Server protocol mismatch
                2009,  # Wrong host info
                2026,  # SSL connection error
        ):
            return _perform_handling('OperationalError')

    # OSError happens on system-related errors, like full disk or getaddrinfo() failure.
    # Catch it and log an extra error for additional context.
    if isinstance(exc, OSError):
        return _perform_handling('OSError')

    if isinstance(exc, UnsupportedRule):
        return _perform_handling('UnsupportedRule')

    return drf_exception_handler(exc, context)
