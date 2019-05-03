import json
from json import JSONDecodeError

from rest_framework.exceptions import APIException


class PDNSException(APIException):

    def __init__(self, response=None, detail=None, status=None):
        self.status_code = status or response.status_code
        if detail:
            self.detail = detail
        else:
            try:
                self.detail = json.loads(response.text)['error']
            except (JSONDecodeError, KeyError):
                self.detail = response.text
