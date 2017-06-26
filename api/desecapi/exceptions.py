from rest_framework.exceptions import APIException
import json


class PdnsException(APIException):

    def __init__(self, response):
        self.status_code = response.status_code
        self.detail = json.loads(response.text)['error']
