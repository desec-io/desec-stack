User Registration and Management
--------------------------------

Getting Started
~~~~~~~~~~~~~~~

Access to the domain management API is granted to registered and logged in users only. User accounts
can register free of charge through the API, providing an email address and a
password. To register an user account, issue a request like this::

    http POST \
        https://desec.io/api/v1/auth/users/ \
        email:='"anemailaddress@example.com"' \
        password:='"yourpassword"'

Your email address is required for account recovery, in case you forgot your
password, for contacting support, etc. It is deSEC's policy to require users
to provide a valid email address so that support requests can be verified.
**If you provide an invalid email address, we will not be able to help you
if you need support.**

Note that while we do not enforce restrictions on your password, please do not
choose a weak one.

Once a user account has been registered, you will be able to log in. Log in is
done by asking the API for a token that can be used to authorize subsequent DNS
management requests. To obtain such a token, send your email address and password to the
``/auth/token/login/`` endpoint::

    http POST \
        https://desec.io/api/v1/auth/token/login/ \
        email:='"anemailaddress@example.com"' \
        password:='"yourpassword"'

The API will reply with a token like::

    {
        "auth_token": "i+T3b1h/OI+H9ab8tRS98stGtURe"
    }

Most interactions with the API require authentication of the domain owner using
this token. To authenticate, the token is transmitted via the HTTP
``Authorization`` header, as shown in the examples in this document.

Additionally, the API provides you with the ``/auth/tokens/`` endpoint which you can
use to create and destroy additional tokens (see below). Such token can be used
to authenticate devices independently of your current login session, such as
routers. They can be revoked individually.


Registration
~~~~~~~~~~~~

The API provides an endpoint to register new user accounts. New accounts
require an email address and a password.

Your email address is required for account recovery, in case you forgot your
password, for contacting support, etc. It is deSEC's policy to require users
to provide a valid email address so that support requests can be verified.
**If you provide an invalid email address, we will not be able to help you
if you need support.**

Note that while we do not enforce restrictions on your password, please do not
choose a weak one.

Upon successful registration, the server will reply with ``201 Created`` and
send you a welcome email. If there is a problem with your email or password,
the server will reply with ``400 Bad Request`` and give a human-readable
error message that may look like::

    HTTP/1.1 400 Bad Request

    {
        "password": [
            "This field may not be blank."
        ]
    }

Your password information will be stored on our servers using `Django's default
method, PBKDF2 <https://docs.djangoproject.com/en/2.1/topics/auth/passwords/>`_.


Preventing Abuse
````````````````

We enforce some limits on user creation requests to make abuse harder. In cases
where our heuristic suspects abuse, the server will still reply with
``201 Created`` but will send you an email asking to solve a
Google ReCaptcha. We implemented this as privacy-friendly as possible, but
recommend solving the captcha using some additional privacy measures such as an
anonymous browser-tab, VPN, etc. Before solving the captcha, the account will
be on hold, that is, it will be possible to log in and issue most requests as
normal; however, any DNS settings will not be deployed to our servers.


Log In
~~~~~~

All interactions with the API that require authentication must be authenticated
using a token that identifies the user and authorizes the request. The process
of obtaining such a token is what we call log in.

To obtain an authentication token, log in by sending your email address and
password to the token create endpoint of the API::

    http POST \
        https://desec.io/api/v1/auth/token/login/ \
        email:='"anemailaddress@example.com"' \
        password:='"yourpassword"'

If email address and password match our records, the server will reply with
``201 Created`` and send you the token as part of the response body::

    {
        "auth_token": "i+T3b1h/OI+H9ab8tRS98stGtURe"
    }

Note that every time you POST to this endpoint, a *new* Token will be created,
while old tokens *remain valid*.

To authorize subsequent requests with the new token, set the HTTP ``Authorization``
header to the token value, prefixed with ``Token``::

    http POST \
        http://desec.io/api/v1/ \
        Authorization:"Token i+T3b1h/OI+H9ab8tRS98stGtURe"


Log Out
~~~~~~~

To invalidate an authentication token (log out), send a ``POST`` request to
the token destroy endpoint, using the token in question in the ``Authorization``
header::

    http POST \
        https://desec.io/api/v1/auth/token/logout/ \
        Authorization:"Token i+T3b1h/OI+H9ab8tRS98stGtURe"

The server will delete the token and respond with ``204 No Content``.


Manage Account
~~~~~~~~~~~~~~

Field Reference
```````````````

A JSON object representing a user has the following structure::

    {
        "dyn": false,
        "email": "address@example.com",
        "limit_domains": 5,
        "locked": false
    }

Field details:

``dyn``
    :Access mode: read-only (deprecated)

    Indicates whether the account is restricted to dynDNS domains under
    dedyn.io.

``email``
    :Access mode: read, write

    Email address associated with the account.  This address must be valid
    in order to submit support requests to deSEC.

``limit_domains``
    :Access mode: read-only

    Maximum number of DNS zones the user can create.

``locked``
    :Access mode: read-only

    Indicates whether the account is locked.  If so, publication of DNS
    record changes will be adjourned.


Retrieve Account Information
````````````````````````````

To request information about your account, send a ``GET`` request to the
``auth/me/`` endpoint::

    http GET \
        https://desec.io/api/v1/auth/me/ \
        Authorization:"Token i+T3b1h/OI+H9ab8tRS98stGtURe"


Change Email Address
````````````````````

You can change your account email address by sending a ``PUT`` request to the
``auth/me/`` endpoint::

    http PUT \
        https://desec.io/api/v1/auth/me/ \
        Authorization:"Token i+T3b1h/OI+H9ab8tRS98stGtURe" \
        email:='"new-email@example.com"'

Please note that our email support only acts upon requests that originate from
the email address associated with the deSEC user in question.  It is therefore
required that you provide a valid email address.  However, we do not
automatically verify the validity of the address provided.

**If you provide an invalid email address and forget your account password and
tokens, we will not be able to help you, and access will be lost permanently.**


Password Reset
``````````````

To reset your account password, you will need to have access to your email
account. It is a two step process. First, let us know you want to reset your
password by issuing a POST request::

    http POST \
        https://desec.io/api/v1/auth/password/reset/ \
        email:='"youremail@example.com"'

The server will respond with ``204 No Content`` regardless of whether the email
address is known or not. If the email address has a user account associated,
we will send an email containing a ``uid`` and a ``token``, encoded into a
URL that will look like this::

    https://desec.io/#/password/reset/confirm/MQ/4zd-1d20102485862f7bae7b

In this example, the ``uid`` is ``MQ``, and ``4zd-1d...`` is the ``token``. To
reset your account password, issue a ``POST`` request containing ``uid``,
``token`` and the new password::

    http POST \
        https://desec.io/api/v1/auth/password/reset/confirm/ \
        uid:='"MQ"' \
        token:='"4zd-1d20102485862f7bae7b"' \
        new_password:='"your new password"'

Please note that the password reset token and the API authentication token are
unrelated and only coincidentally carry the same name. (Sorry about that!)


Manage Tokens
~~~~~~~~~~~~~

To make authentication more flexible, the API can provide you with multiple
authentication tokens. To that end, we provide a set of token management
endpoints that are separate from the above-mentioned log in and log out
endpoints. The most notable difference is that the log in endpoint needs
authentication with email address and password, whereas the token management
endpoint is authenticated using already issued tokens.


Retrieving All Current Tokens
`````````````````````````````

To retrieve a list of currently valid tokens, issue a ``GET`` request::

    http \
        https://desec.io/api/v1/auth/tokens/ \
        Authorization:"Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will respond with a list of token objects, each containing a
timestamp when the token was created (note the ``Z`` indicating the UTC
timezone), an ID to identify that token, as well as the secret token value
itself. Each token can carry a name that has no operational
relevance to the API and is for user reference only. All tokens created
by the log in endpoint will have "login" as name.

::

    [
        {
            "created": "2018-09-06T07:05:54.080564Z",
            "id": 14423,
            "value": "4yScSMFFNdAlk6WZuLIwYBVYnXPF",
            "name": "login"
        },
        {
            "created": "2018-09-06T08:53:26.428396Z",
            "id": 36483,
            "value": "mu4W4MHuSc0HyrGD1h/dnKuZBond",
            "name": ""
        }
    ]


Create Additional Tokens
````````````````````````

To create another token using the token management interface, issue a
``POST`` request to the same endpoint::

    http POST \
        https://desec.io/api/v1/auth/tokens/ \
        Authorization:"Token mu4W4MHuSc0HyrGD1h/dnKuZBond" \
        name:='"my new token"'

Note that the name is optional and will be empty if not specified. The server
will reply with ``201 Created`` and the created token in the response body::

    {
        "created": "2018-09-06T09:08:43.762697Z",
        "id": 73658,
        "value": "4pnk7u+NHvrEkFzrhFDRTjGFyX+S",
        "name": "my new token"
    }


Delete Tokens
`````````````

To delete an existing token via the token management endpoints, issue a
``DELETE`` request on the token's endpoint::

    http DELETE \
        https://desec.io/api/v1/auth/tokens/:id/ \
        Authorization:"Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

Note that, for now, all tokens have equal power -- every token can authorize
any action. We may implement specialized tokens in the future.


Token Security Considerations
`````````````````````````````

This section is for information only. Token length and encoding may be subject
to change in the future.

Any token is generated from 168 bits of true randomness at the server. Guessing
the token correctly is hence practically impossible. The value corresponds to 21
bytes and is represented by 28 characters in Base64-like encoding. That is, any token
will only consist of URL-safe characters ``A-Z``, ``a-z``, ``-``, and ``.``. (We do not
have any padding at the end because the string length is a multiple of 4.)

As all tokens are stored in plain text on the server, the user may not choose
the token value individually to prevent re-using passwords as tokens at deSEC.

Old versions of deSEC encoded 20-byte tokens in 40 characters with hexadecimal
representation. Such tokens will not be issued anymore, but remain valid until
invalidated by the user.
