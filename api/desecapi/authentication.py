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

from desecapi.models import Token
from desecapi.serializers import AuthenticatedBasicUserActionSerializer, EmailPasswordSerializer


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
            username, key = base64.b64decode(basic).decode(HTTP_HEADER_ENCODING).split(':')
            user, token = TokenAuthentication().authenticate_credentials(key)
            domain_names = user.domains.values_list('name', flat=True)
            if username not in ['', user.email] and not username.lower() in domain_names:
                raise Exception
        except Exception:
            raise exceptions.AuthenticationFailed(invalid_token_message)

        if not user.is_active:
            raise exceptions.AuthenticationFailed(invalid_token_message)

        return user, token

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

        if 'username' not in request.query_params:
            msg = 'No username URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)
        if 'password' not in request.query_params:
            msg = 'No password URL parameter provided.'
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(request.query_params['username'], request.query_params['password'])

    def authenticate_credentials(self, _, key):
        try:
            user, token = TokenAuthentication().authenticate_credentials(key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('badauth')

        if not user.is_active:
            raise exceptions.AuthenticationFailed('badauth')

        return token.user, token


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
        serializer = AuthenticatedBasicUserActionSerializer(data=request.data, context=view.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['user'], None


class TokenHasher(PBKDF2PasswordHasher):
    algorithm = 'pbkdf2_sha256_iter1'
    iterations = 1
