from rest_framework.exceptions import APIException
import json


class PdnsException(APIException):

    def __init__(self, response=None, detail=None, status=None):
        self.status_code = status or response.status_code
        if detail:
            self.detail = detail
        else:
            try:
                self.detail = json.loads(response.text)['error']
            except:
                self.detail = response.text
