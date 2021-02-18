import base64
from ipaddress import ip_address

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.utils import timezone
from rest_framework import exceptions, HTTP_HEADER_ENCODING
from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header,
    TokenAuthentication as RestFrameworkTokenAuthentication,
    BasicAuthentication)

from desecapi.models import Domain, Token
from desecapi.serializers import AuthenticatedBasicUserActionSerializer, EmailPasswordSerializer


class DynAuthenticationMixin:
    def authenticate_credentials(self, username, key):
        user, token = TokenAuthentication().authenticate_credentials(key)
        # Make sure username is not misleading
        try:
            if username in ['', user.email] or Domain.objects.filter_qname(username.lower(), owner=user).exists():
                return user, token
        except ValueError:
            pass
        raise exceptions.AuthenticationFailed


class TokenAuthentication(RestFrameworkTokenAuthentication):
    model = Token

    # Note: This method's runtime depends on in what way a credential is invalid (expired, wrong client IP).
    # It thus exposes the failure reason when under timing attack.
    def authenticate(self, request):
        try:
            user, token = super().authenticate(request)  # may raise exceptions.AuthenticationFailed if token is invalid
        except TypeError:  # if no token was given
            return None  # unauthenticated

        if not token.is_valid:
            raise exceptions.AuthenticationFailed('Invalid token.')

        token.last_used = timezone.now()
        token.save()

        # REMOTE_ADDR is populated by the environment of the wsgi-request [1], which in turn is set up by nginx as per
        # uwsgi_params [2]. The value of $remote_addr finally is given by the network connection [3].
        # [1]: https://github.com/django/django/blob/stable/3.1.x/django/core/handlers/wsgi.py#L77
        # [2]: https://github.com/desec-io/desec-stack/blob/62820ad/www/conf/sites-available/90-desec.api.location.var#L11
        # [3]: https://nginx.org/en/docs/http/ngx_http_core_module.html#var_remote_addr
        # While the request.META dictionary contains a mixture of values from various sources, HTTP headers have keys
        # with the HTTP_ prefix. Client addresses can therefore not be spoofed through headers.
        # In case the stack is run behind an application proxy, the address will be the proxy's address. Extracting the
        # real client address is currently not supported. For further information on this case, see
        # https://www.django-rest-framework.org/api-guide/throttling/#how-clients-are-identified
        client_ip = ip_address(request.META.get('REMOTE_ADDR'))

        # This can likely be done within Postgres with django-postgres-extensions (client_ip <<= ANY allowed_subnets).
        # However, the django-postgres-extensions package is unmaintained, and the GitHub repo has been archived.
        if not any(client_ip in subnet for subnet in token.allowed_subnets):
            raise exceptions.AuthenticationFailed('Invalid token.')

        return user, token

    def authenticate_credentials(self, key):
        key = Token.make_hash(key)
        return super().authenticate_credentials(key)


class BasicTokenAuthentication(BaseAuthentication, DynAuthenticationMixin):
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

        try:
            username, key = base64.b64decode(auth[1]).decode(HTTP_HEADER_ENCODING).split(':')
            return self.authenticate_credentials(username, key)
        except Exception:
            raise exceptions.AuthenticationFailed("badauth")

    def authenticate_header(self, request):
        return 'Basic'


class URLParamAuthentication(BaseAuthentication, DynAuthenticationMixin):
    """
    Authentication against username/password as provided in URL parameters.
    """
    model = Token

    def authenticate(self, request):
        """
        Returns `(User, Token)` if a correct username and token have been supplied
        using URL parameters.  Otherwise raises `AuthenticationFailed`.
        """

        if 'username' not in request.query_params:
            msg = 'No username URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)
        if 'password' not in request.query_params:
            msg = 'No password URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)

        try:
            return self.authenticate_credentials(request.query_params['username'], request.query_params['password'])
        except Exception:
            raise exceptions.AuthenticationFailed("badauth")


class EmailPasswordPayloadAuthentication(BaseAuthentication):
    authenticate_credentials = BasicAuthentication.authenticate_credentials

    def authenticate(self, request):
        serializer = EmailPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.authenticate_credentials(serializer.data['email'], serializer.data['password'], request)


class AuthenticatedBasicUserActionAuthentication(BaseAuthentication):
    """
    Authenticates a request based on whether the serializer determines the validity of the given verification code
    and additional data (using `serializer.is_valid()`). The serializer's input data will be determined by (a) the
    view's 'code' kwarg and (b) the request payload for POST requests.

    If the request is valid, the AuthenticatedAction instance will be attached to the request as `auth` attribute.
    """
    def authenticate(self, request):
        view = request.parser_context['view']
        serializer = AuthenticatedBasicUserActionSerializer(data={}, context=view.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['user'], None


class TokenHasher(PBKDF2PasswordHasher):
    algorithm = 'pbkdf2_sha256_iter1'
    iterations = 1
