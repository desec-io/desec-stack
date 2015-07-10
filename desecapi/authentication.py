from __future__ import unicode_literals
import base64

from rest_framework import exceptions, HTTP_HEADER_ENCODING
from rest_framework.authtoken.models import Token
from rest_framework.authentication import BaseAuthentication, get_authorization_header


class BasicTokenAuthentication(BaseAuthentication):
    """
    HTTP Basic authentication that uses username and token.

    Clients should authenticate by passing the username and the token as a
    password in the "Authorization" HTTP header, according to the HTTP
    Basic Authentication Scheme

        Authorization: Basic dXNlcm5hbWU6dG9rZW4=

    For username "username" and password "token".
    """

    model = Token
    """
    A custom token model may be used, but must have the following properties.

    * key -- The string identifying the token
    * user -- The user to which the token belongs
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'basic':
            return None

        if len(auth) == 1:
            msg = 'Invalid basic auth token header. No credentials provided.'
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid basic auth token header. Basic authentication string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(auth[1])

    def authenticate_credentials(self, basic):
        try:
            user, key = base64.b64decode(basic).decode(HTTP_HEADER_ENCODING).split(':')
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid basic auth token')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted')

        return token.user, token

    def authenticate_header(self, request):
        return 'Basic'