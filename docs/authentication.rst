User Registration and Management
--------------------------------

Manage Account
~~~~~~~~~~~~~~

Access to the domain management API is granted to registered and logged in
users only. Users can register an account free of charge through the API as
described below.

Obtain a Captcha
```````````````````

Before registering a user account, you need to solve a captcha. You will have
to send the captcha ID and solution along with your registration request. To
obtain a captcha, issue a ``POST`` request as follows::

    curl -X POST https://desec.io/api/v1/captcha/

The response body will be a JSON object with an ``id`` and a ``challenge``
field. The value of the ``id`` field is the one that you need to fill into the
corresponding field of the account registration request. The value of the
``challenge`` field is the base64-encoded PNG representation of the captcha
itself. You can display it by directing your browser to the URL
``data:image/png;base64,<challenge>``, after replacing ``<challenge>`` with
the value of the ``challenge`` response field.

Captchas expire after 24 hours. IDs are also invalidated after using them in
a registration request. This means that if you send an incorrect solution,
you will have to obtain a fresh captcha and try again.


Register Account
````````````````

You can register an account by sending a ``POST`` request containing your
email address, a password, and a captcha ID and solution (see `Obtain a
Captcha`_), like this::

    curl -X POST https://desec.io/api/v1/auth/ \
        --header "Content-Type: application/json" --data @- <<EOF
        {
          "email": "youremailaddress@example.com",
          "password": "yourpassword",
          "captcha": {
            "id": "00010203-0405-0607-0809-0a0b0c0d0e0f",
            "solution": "12H45"
          }
        }
    EOF

Please consider the following when registering an account:

- Surrounding whitespace is stripped automatically from passwords.

- We do not enforce restrictions on your password. However, to maintain a high
  level of security, make sure to choose a strong password. It is best to
  generate a long random string consisting of at least 16 alphanumeric
  characters, and use a password manager instead of attempting to remember it.

- If you do not require a password at the moment, you can pass ``null`` (the
  JSON value, not the string!). If you create an account this way, it will not
  be possible to `Log In`_. You can set a password later using the `Password
  Reset`_ procedure.

- Your email address is required for account recovery in case you forgot your
  password, for contacting support, etc. We also send out announcements for
  technical changes occasionally. It is thus deSEC's policy to require users
  provide a valid email address.

When attempting to register a user account, the server will reply with ``202
Accepted``. In case there already is an account for that email address,
nothing else will be done. Otherwise, you will receive an email with a
verification link of the form
``https://desec.io/api/v1/v/activate-account/<code>/``. To activate your
account, send a ``GET`` request using this link (i.e., you can simply click
it). The link expires after 12 hours.

If there is a problem with your email address, your password, or the proposed
captcha solution, the server will reply with ``400 Bad Request`` and give a
human-readable error message that may look like::

    HTTP/1.1 400 Bad Request

    {
        "password": [
            "This field may not be blank."
        ]
    }


Zone Creation during Account Registration
*****************************************

**Note:** The following functionality is intended for internal deSEC use only.
Availability of this functionality may change without notice.

Along with your account creation request, you can provide a domain name as
follows::

    curl -X POST https://desec.io/api/v1/auth/ \
        --header "Content-Type: application/json" --data @- <<EOF
        {
          "email": "youremailaddress@example.com",
          "password": "yourpassword",
          "captcha": {
            "id": "00010203-0405-0607-0809-0a0b0c0d0e0f",
            "solution": "12H45"
          },
          "domain": "example.org"
        }
    EOF

If the ``domain`` field is present in the request payload, a DNS zone will be
created for this domain name once you activate your account using the
verification link that we will send to your email address. If the zone cannot
be created (for example, because the domain name is unavailable), your account
will be deleted, and you can start over with a fresh registration.


Log In
``````

All interactions with the API that require authentication must be authenticated
using a token that identifies the user and authorizes the request. Logging in
is the process of obtaining such a token.

In order to log in, you need to confirm your email address first. Afterwards,
you can ask the API for a token that can be used to authorize subsequent DNS
management requests. To obtain such a token, send a ``POST`` request with your
email address and password to the ``/auth/login/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/login/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"email": "youremailaddress@example.com", "password": "yourpassword"}'

If email address and password match our records, the server will reply with
``201 Created`` and send you the token as part of the response body::

    {"auth_token": "i-T3b1h_OI-H9ab8tRS98stGtURe"}

In case of credential mismatch, the server replies with ``401 Unauthorized``.

**Note:** Every time you send a ``POST`` request to this endpoint, an
additional token will be created. Existing tokens will *remain valid*.

To authorize subsequent requests with the new token, set the HTTP ``Authorization``
header to the token value, prefixed with ``Token``::

    curl -X GET https://desec.io/api/v1/ \
        --header "Authorization: Token i-T3b1h_OI-H9ab8tRS98stGtURe"


Retrieve Account Information
````````````````````````````

To request information about your account, send a ``GET`` request to the
``/auth/account/`` endpoint::

    curl -X GET https://desec.io/api/v1/auth/account/ \
        --header "Authorization: Token i-T3b1h_OI-H9ab8tRS98stGtURe"

A JSON object representing your user account will be returned::

    {
        "created": "2019-10-16T18:09:17.715702Z",
        "email": "youremailaddress@example.com",
        "id": "9ab16e5c-805d-4ab1-9030-af3f5a541d47",
        "limit_domains": 5
    }

Field details:

``created``
    :Access mode: read-only

    Registration timestamp.

``email``
    :Access mode: read-only

    Email address associated with the account.

``id``
    :Access mode: read-only

    User ID.

``limit_domains``
    :Access mode: read-only

    Maximum number of DNS zones the user can create.


Password Reset
``````````````

In case you forget your password, you can reset it. To do so, send a
``POST`` request with your email address to the
``/auth/account/reset-password/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/account/reset-password/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"email": "youremailaddress@example.com"}'

The server will reply with ``202 Accepted``. If there is no account associated
with this email address, nothing else will be done. Otherwise, you will receive
an email with a URL of the form
``https://desec.io/api/v1/v/reset-password/<code>/``. To perform the actual
password reset, send a ``POST`` request to this URL, with the new password in
the payload::

    curl -X POST https://desec.io/api/v1/v/reset-password/<code>/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"new_password": "yournewpassword"}'

This URL expires after 12 hours. It is also invalidated by certain other
account-related activities, such as changing your email address.

Once the password was reset successfully, we will send you an email informing
you of the event.

Password Change
```````````````

To change your password, please follow the instructions for `Password Reset`_.


Change Email Address
````````````````````

To change the email address associated with your account, send a ``POST``
request with your email address, your password, and your new email address to
the ``/auth/account/change-email/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/account/change-email/ \
        --header "Content-Type: application/json" --data @- <<EOF
        {
          "email": "youremailaddress@example.com",
          "password": "yourpassword",
          "new_email": "anotheremailaddress@example.net"
        }
    EOF

If the correct password has been provided, the server will reply with ``202
Accepted``. In case there already is an account for the email address given in
the ``new_email`` field, nothing else will be done. Otherwise, we will send
an email to the new email address for verification purposes. It will contain a
link of the form ``https://desec.io/api/v1/v/change-email/<code>/``. To perform
the actual change, send a ``GET`` request using this link (i.e., you can simply
click the link).

The link expires after 12 hours. It is also invalidated by certain other
account-related activities, such as changing your password.

Once the email address was changed successfully, we will send a message to the
old email address for informational purposes.


Delete Account
``````````````

Before you can delete your account, it is required to first delete all your
domains from deSEC (see `Deleting a Domain`_).

To delete your (empty) account, send a ``POST`` request with your email
address and password to the ``/auth/account/delete/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/account/delete/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"email": "youremailaddress@example.com", "password": "yourpassword"}'

If the correct password has been provided, the server will reply with ``202
Accepted`` and send you an email with a link of the form
``https://desec.io/api/v1/v/delete-account/<code>/``. To finish the deletion,
send a ``GET`` request using this link (i.e., you can simply click the link).

The link expires after 12 hours. It is also invalidated by certain other
account-related activities, such as changing your email address or password.

If your account still contains domains, the server will respond with ``409
Conflict`` and not delete your account.


Log Out
```````

To invalidate an authentication token (log out), send a POST request to the
the log out endpoint::

    curl -X POST https://desec.io/api/v1/auth/logout/ \
        --header "Authorization: Token i-T3b1h_OI-H9ab8tRS98stGtURe"

To delete other tokens based on their ID, see `Delete Tokens`_.


Security Considerations
```````````````````````

Confirmation Codes
    Some account-related activities require the user to explicitly reaffirm her
    intent. For this purpose, we send a link with a confirmation code to the
    user's email address. Although clients generally should consider these
    codes opaque, we would like to give some insights into how they work.

    The code is a base64-encoded JSON representation of the user's intent.
    The representation carries a timestamp of when the intent was expressed,
    the user ID, and also any extra parameters that were submitted along with
    the intent. An example of such a parameter is the new email address in the
    context of a `change email address`_ operation. Parameters that are
    unknown at the time when the code is generated are not included in the
    code and must be provided via ``POST`` request payload when using the
    code. A typical example of this is the new password in a `password reset`_
    operation, as it is only provided when the code is being used (and not at
    the time when the code is requested).

    To ensure integrity, we also include a message authentication code (MAC)
    using `Django's signature implementation
    <https://docs.djangoproject.com/en/2.2/_modules/django/core/signing/#Signer>`_.
    When a confirmation code is used, we recompute the MAC based on the data
    incorporated in the code, and only perform the requested action if the MAC
    is reproduced identically. Codes are also checked for freshness using the
    timestamp, and rejected if older than allowed.

    In order to prevent race conditions, we add additional data to the MAC
    input such that codes are only valid as long as the user state is not
    modified (e.g. by performing another sensitive account operation). This is
    achieved by mixing a) the account operation type (e.g. password reset), b)
    the account's activation status, c) the account's current email address,
    and d) the user's password hash into the MAC input. If any of these
    parameters happens to change before a code is applied, the MAC will be
    rendered invalid, and the operation will fail. This measure blocks
    scenarios such as using an old email address change code after a more
    recent password change.

    This approach allows us to securely authenticate sensitive user operations
    without keeping a list of requested operations on the server. This is both
    an operational and a privacy advantage. For example, if the user expresses
    her intent to change the account email address, we do not store that new
    address on the server until the confirmation code is used (from which the
    new address is then extracted).

Email verification
    Operations that require verification of a new email address (such as when
    registering first), the server response does not depend on whether another
    user is already using that address. This is to prevent clients from
    telling whether a certain email address is registered with deSEC or not.

    Verification emails will only be sent out if the email address is not yet
    associated with an account. Otherwise, nothing will happen.

    Also, accounts are created on the server side when the registration
    request is received (and kept in inactive state). That is, state exists
    on the server even before the email address is confirmed. Confirmation
    merely activates the existing account. The purpose of this is to avoid
    running the risk of sending out large numbers of emails to the same
    address when a client decides to send multiple registration requests for
    the same address. In this case, no emails will be sent after the first
    one.

Password Security
    Password information is stored using `Django's default method, PBKDF2
    <https://docs.djangoproject.com/en/2.1/topics/auth/passwords/>`_.


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

    curl -X GET https://desec.io/api/v1/auth/tokens/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will respond with a list of token objects, each containing a
timestamp when the token was created (note the ``Z`` indicating the UTC
timezone) and a UUID to identify that token. Furthermore, each token can
carry a name that is of no operational relevance to the API (it is meant
for user reference only). Certain API operations (such as login) will
automatically populate the ``name`` field with values such as "login" or
"dyndns".

::

    [
        {
            "created": "2018-09-06T07:05:54.080564Z",
            "id": "3159e485-5499-46c0-ae2b-aeb84d627a8e",
            "name": "login"
        },
        {
            "created": "2018-09-06T08:53:26.428396Z",
            "id": "76d6e39d-65bc-4ab2-a1b7-6e94eee0a534",
            "name": ""
        }
    ]

You can also retrieve an individual token by appending ``:id/`` to the URL,
for example in order to look up a token's name or creation timestamp.


Create Additional Tokens
````````````````````````

To create another token using the token management interface, issue a
``POST`` request to the same endpoint::

    curl -X POST https://desec.io/api/v1/auth/tokens/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "my new token"}'

Note that the name is optional and will be empty if not specified. The server
will reply with ``201 Created`` and the created token in the response body::

    {
        "created": "2018-09-06T09:08:43.762697Z",
        "id": "3a6b94b5-d20e-40bd-a7cc-521f5c79fab3",
        "token": "4pnk7u+NHvrEkFzrhFDRTjGFyX+S",
        "name": "my new token"
    }


Delete Tokens
`````````````

To delete an existing token by its ID via the token management endpoints, issue a
``DELETE`` request on the token's endpoint, replacing ``:id`` with the
token ``id`` value::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/:id/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

If you do not have the token UUID, but you do have the token value itself, you
can use the `Log Out`_ endpoint to delete it.

Note that, for now, all tokens have equal power -- every token can authorize
any action. We are planning to implement scoped tokens in the future.


Token Security Considerations
`````````````````````````````

This section is for information only. Token length and encoding may change in
the future.

Any token is generated from 168 bits of randomness at the server and stored in
hashed format (PBKDF2-HMAC-SHA256). Guessing the token correctly or reversing
the hash is hence practically impossible.

The token value is represented by 28 characters using a URL-safe variant of
base64 encoding. It comprises only the characters ``A-Z``, ``a-z``, ``0-9``, ``-``,
and ``_``. (Base64 padding is not needed as the string length is a multiple of 4.)

Old versions of the API encoded 20-byte tokens in 40 characters with hexadecimal
representation. Such tokens will not be issued anymore, but remain valid until
invalidated by the user.
