.. _manage-account:

Manage Account
~~~~~~~~~~~~~~

Access to the domain management API is granted to registered and logged in
users only. Users can register an account free of charge through the API as
described below.


.. _obtain-a-captcha:

Obtain a Captcha
````````````````

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


.. _register-account:

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
  provide an email address and to confirm its validity by clicking a
  verification link sent to that address.

- To facilitate automatic sign-ups, the ``captcha`` field in the registration
  request can be omitted; in this case, the field is required later when
  completing email verification. In case we find this to cause adverse effects
  on our systems, we may adopt a captcha-on-registration policy at any time.

When attempting to register a user account, the server will reply with ``202
Accepted``. In case there already is an account for that email address,
nothing else will be done. Otherwise, you will receive an email with a
verification link of the form
``https://desec.io/api/v1/v/activate-account/<code>/``. To activate your
account, click on that link (which will direct you to our frontend) or send a
``POST`` request on the command line. (If a captcha was not provided during
registration, it has to be provided now.) The link expires after 12 hours.

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


.. _log-in:

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
``200 OK`` and return the token in the ``token`` field of the response body::

    {
        "created": "2018-09-06T09:07:43.762697Z",
        "id": "8f9cbae2-c862-48a4-b3f0-2cb1a80df168",
        "token": "f07Q0TRmEb-CRWPe4h64_iV2jbet",
        "name": "login"
    }

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
        "limit_domains": 15
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
``POST`` request with your email address and a captcha ID and solution (see
`Obtain a Captcha`_) to the ``/auth/account/reset-password/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/account/reset-password/ \
        --header "Content-Type: application/json" --data @- <<EOF
        {
          "email": "youremailaddress@example.com",
          "captcha": {
            "id": "00010203-0405-0607-0809-0a0b0c0d0e0f",
            "solution": "12H45"
          }
        }
    EOF

The server will reply with ``202 Accepted``. If there is no account associated
with this email address, nothing else will be done. Otherwise, you will receive
an email with a URL of the form
``https://desec.io/api/v1/v/reset-password/<code>/``. To perform the actual
password reset, click on that link (which will direct you to our frontend) or
send a ``POST`` request to this URL, with the new password in
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
the actual change, click on that link (which will direct you to our frontend)
or send a ``POST`` request on the command line.

The link expires after 12 hours. It is also invalidated by certain other
account-related activities, such as changing your password.

Once the email address was changed successfully, we will send a message to the
old email address for informational purposes.


Delete Account
``````````````

Before you can delete your account, it is required to first delete all your
domains from deSEC (see :ref:`deleting-a-domain`).

To delete your (empty) account, send a ``POST`` request with your email
address and password to the ``/auth/account/delete/`` endpoint::

    curl -X POST https://desec.io/api/v1/auth/account/delete/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"email": "youremailaddress@example.com", "password": "yourpassword"}'

If the correct password has been provided, the server will reply with ``202
Accepted`` and send you an email with a link of the form
``https://desec.io/api/v1/v/delete-account/<code>/``. To finish the deletion,
click on that link (which will direct you to our frontend) or send a ``POST``
request on the command line.

The link expires after 12 hours. It is also invalidated by certain other
account-related activities, such as changing your email address or password.

If your account still contains domains, the server will respond with ``409
Conflict`` and not delete your account.


.. _log-out:

Log Out
```````

To invalidate an authentication token (log out), send a POST request to the
the log out endpoint::

    curl -X POST https://desec.io/api/v1/auth/logout/ \
        --header "Authorization: Token i-T3b1h_OI-H9ab8tRS98stGtURe"

To delete other tokens based on their ID, see :ref:`delete-tokens`.


Security Considerations
```````````````````````

Confirmation Codes
    Some account-related activities require the user to explicitly reaffirm her
    intent. For this purpose, we send a link with a confirmation code to the
    user's email address. Although clients generally should consider these
    codes opaque, we would like to give some insights into how they work.

    The code is a base64-encoded encrypted-then-signed JSON representation of
    the user's intent. Encryption/decryption and authentication (sign/verify)
    is handled by `pyca/cryptography's Fernet implementation
    <https://cryptography.io/en/latest/fernet/>`_ which is uses AES-CBC and
    HMAC-SHA256 with specifically derived key material. The HMAC also signs the
    current time (i.e. when the intent was expressed). During verification,
    codes are checked for freshness and rejected when older than allowed.

    The encoded intent is composed of the user ID and any extra parameters that
    were submitted along with the intent. An example of such a parameter is the
    new email address in the context of a `change email address`_ operation.
    Parameters that are unknown at code generation time are not included in the
    code and must be provided via ``POST`` request payload when using the code.
    A typical example of this is the new password in a `password reset`_
    operation, as it is only provided when the code is being used (and not at
    the time when the code is requested).

    In order to prevent race conditions, we augment the code with additional
    data which we use to invalidate codes when the user state is modified (e.g.
    by performing another sensitive account operation). This is achieved by
    including the combined hash of a) the account operation type (e.g. password
    reset), b) the account's activation status, c) the account's current email
    address, and d) the user's password hash. When a confirmation code is used,
    we recompute this hash based on the user's current state, and only perform
    the requested action if the hash is reproduced identically. If any of these
    parameters happens to change before a code is applied, the code will be
    rendered invalid, and the operation will fail. This measure blocks
    scenarios such as using an old email address change code after a more
    recent password change. (Note that it is sometimes possible to revert the
    state so that an old code becomes valid again, such as when you change the
    email address twice, with the second change undoing the first one. This
    issue does not occur for password changes; those do permanently invalidate
    other codes.)

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
