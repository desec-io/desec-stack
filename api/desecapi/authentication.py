from __future__ import unicode_literals
import base64
from rest_framework import exceptions, HTTP_HEADER_ENCODING
from rest_framework.authentication import BaseAuthentication, get_authorization_header, authenticate
from desecapi.models import Token
from rest_framework.authentication import TokenAuthentication as RestFrameworkTokenAuthentication


class TokenAuthentication(RestFrameworkTokenAuthentication):
    model = Token


class BasicTokenAuthentication(BaseAuthentication):
    """
    HTTP Basic authentication that uses username and token.

    Clients should authenticate by passing the username and the token as a
    password in the "Authorization" HTTP header, according to the HTTP
    Basic Authentication Scheme

        Authorization: Basic dXNlcm5hbWU6dG9rZW4=

    For username "username" and password "token".
    """

    # A custom token model may be used, but must have the following properties.
    #
    # * key -- The string identifying the token
    # * user -- The user to which the token belongs
    model = Token

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
        invalid_token_message = 'Invalid basic auth token'
        try:
            user, key = base64.b64decode(basic).decode(HTTP_HEADER_ENCODING).split(':')
            token = self.model.objects.get(key=key)
        except:
            raise exceptions.AuthenticationFailed(invalid_token_message)

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(invalid_token_message)

        return token.user, token

    def authenticate_header(self, request):
        return 'Basic'


class URLParamAuthentication(BaseAuthentication):
    """
    Authentication against username/password as provided in URL parameters.
    """
    model = Token

    def authenticate(self, request):
        """
        Returns a `User` if a correct username and password have been supplied
        using URL parameters.  Otherwise returns `None`.
        """

        if not 'username' in request.query_params:
            msg = 'No username URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)
        if not 'password' in request.query_params:
            msg = 'No password URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(request.query_params['username'], request.query_params['password'])

    def authenticate_credentials(self, userid, key):
        try:
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('badauth')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('badauth')

        return token.user, token
