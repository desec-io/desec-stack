from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler
import logging


def handle_db_unavailable(exc, context):
    """
    desecapi specific exception handling. If no special treatment is applied,
    we default to restframework's exception handling. See also
    https://www.django-rest-framework.org/api-guide/exceptions/#custom-exception-handling
    """

    if isinstance(exc, OperationalError):
        if isinstance(exc.args, (list, dict, tuple)) and exc.args and \
            exc.args[0] in (
                2002,  # Connection refused (Socket)
                2003,  # Connection refused (TCP)
                2005,  # Unresolved host name
                2007,  # Server protocol mismatch
                2009,  # Wrong host info
                2026,  # SSL connection error
        ):
            logging.getLogger('django.request').error('OperationalError Supplementary Information',
                                                      exc_info=exc, stack_info=False)

            # Gracefully let clients know that we cannot connect to the database
            data = {'detail': 'Please try again later.'}

            return Response(data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return exception_handler(exc, context)
