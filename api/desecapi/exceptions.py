from rest_framework import status
from rest_framework.exceptions import APIException


class AuthenticatedActionInvalidState(Exception):
    message = (
        "This action cannot be carried out because another operation has been performed, "
        "invalidating this one. (Are you trying to perform this action twice?)"
    )


class RequestEntityTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Payload too large."
    default_code = "too_large"


class ExternalAPIException(APIException):
    def __init__(self, response=None):
        self.response = response
        detail = (
            f"pdns response code: {response.status_code}, body: {response.text}"
            if response is not None
            else None
        )
        return super().__init__(detail)


class PDNSException(ExternalAPIException):
    pass


class PCHException(ExternalAPIException):
    pass


class KnotException(APIException):
    pass


class ConcurrencyException(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many concurrent requests."
    default_code = "concurrency_conflict"
