.. _manage-tokens:

Manage Tokens
~~~~~~~~~~~~~

To make authentication more flexible, you can create and configure multiple
authentication tokens. To that end, we provide a set of token management
endpoints that are separate from the login and logout endpoints. The most
notable differences are that the login endpoint needs authentication with
the user credentials (email address and password) and its purpose is to return
a token with a broad range of permissions, whereas the token management
endpoints are authenticated using an already issued token, for the purpose of
configuring more fine-grained token permissions.

When accessing the token management endpoints using a token without sufficient
permission, the server will reply with ``403 Forbidden``.


.. _`token object`:

Token Field Reference
`````````````````````

A JSON object representing a token has the following structure::

    {
        "created": "2018-09-06T09:08:43.762697Z",
        "id": "3a6b94b5-d20e-40bd-a7cc-521f5c79fab3",
        "last_used": null,
        "name": "my new token",
        "perm_manage_tokens": false,
        "allowed_subnets": [
            "0.0.0.0/0",
            "::/0"
        ],
        "max_age": "365 00:00:00",
        "max_unused_period": null,
        "token": "4pnk7u-NHvrEkFzrhFDRTjGFyX_S"
    }

Field details:

``allowed_subnets``
    :Access mode: read, write
    :Type: Array of IPs or IP subnets

    Exhaustive list of IP addresses or subnets clients must connect from in
    order to successfully authenticate with the token.  Both IPv4 and IPv6 are
    supported.  Defaults to ``0.0.0.0/0, ::/0`` (no restriction).

``created``
    :Access mode: read-only
    :Type: timestamp

    Timestamp of token creation, in ISO 8601 format (e.g.
    ``2018-09-06T09:08:43.762697Z``).

``id``
    :Access mode: read-only
    :Type: UUID

    Token ID, used for identification only (e.g. when deleting a token). This
    is *not* the token value.

``is_valid``
    :Access mode: read-only
    :Type: boolean

    Indicates whether this token is valid.  Currently, this reflects validity
    based on ``max_age`` and ``max_unused_period``.

``last_used``
    :Access mode: read-only
    :Type: timestamp or ``null``

    Timestamp of when the token was last successfully authenticated, or
    ``null`` if the token has never been used.

    In most cases, this corresponds to the last time when an API operation
    was performed using this token.  However, if the operation was not
    executed because it was found that the token did not have sufficient
    permission, this field will still be updated.

``max_age``
    :Access mode: read, write
    :Type: string (time duration: ``[DD] [HH:[MM:]]ss[.uuuuuu]``) or ``null``

    Maximum token age.  If ``created + max_age`` is less than the current time,
    the token is invalidated.  Invalidated tokens are not automatically deleted
    and can be resurrected by adjusting the expiration settings (using another
    valid token with sufficient privileges).

    If ``null``, the token is valid regardless of age (setting disabled).

``max_unused_period``
    :Access mode: read, write
    :Type: string (time duration: ``[DD] [HH:[MM:]]ss[.uuuuuu]``) or ``null``

    Maximum allowed time period of disuse without invalidating the token.  If
    ``max(created, last_used) + max_unused_period`` is less than the current
    time, the token is invalidated.  Invalidated tokens are not automatically
    deleted and can be resurrected by adjusting the expiration settings (using
    another valid token with sufficient privileges).

    If ``null``, the token is valid regardless of prior usage (setting
    disabled).

``name``
    :Access mode: read, write
    :Type: string

    Token name.  It is meant for user reference only and carries no
    operational meaning.  If omitted, the empty string is assumed.
    The maximum length is 178.

    Certain API operations will automatically populate the ``name`` field with
    suitable values such as "login" or "dyndns".

``perm_manage_tokens``
    :Access mode: read, write
    :Type: boolean

    Permission to manage tokens (this one and also all others).  A token which
    does not have this flag set cannot access the ``auth/tokens/`` endpoints.

``token``
    :Access mode: read-once
    :Type: string

    Token value that is used to authenticate API requests.  It is only
    returned once, upon creation of the token.  The value of an existing token
    cannot be recovered (we store it in irreversibly hashed form).  For
    security details, see `Security Considerations`_.


Creating a Token
````````````````

To create a new token, issue a ``POST`` request to the tokens endpoint::

    curl -X POST https://desec.io/api/v1/auth/tokens/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "my new token"}'

Note that the name and other fields are optional.  The server will reply with
``201 Created`` and the created token in the response body::

    {
        "created": "2018-09-06T09:08:43.762697Z",
        "id": "3a6b94b5-d20e-40bd-a7cc-521f5c79fab3",
        "last_used": null,
        "name": "my new token",
        "perm_manage_tokens": false,
        "allowed_subnets": [
            "0.0.0.0/0",
            "::/0"
        ],
        "token": "4pnk7u-NHvrEkFzrhFDRTjGFyX_S"
    }

The new token will, by default, possess fewer permissions than a login token.
In particular, the ``perm_manage_tokens`` flag will not be set, so that the
new token cannot be used to retrieve, modify, or delete any tokens (including
itself).

With the default set of permissions, tokens qualify for carrying out all API
operations related to DNS management (i.e. managing both domains and DNS
records).  Note that it is always possible to use the :ref:`log-out` endpoint
to delete a token.

If you require tokens with extra permissions, you can provide the desired
configuration during creation:

- ``allowed_subnets``:  In this field, you can list the IP addresses (or
  subnets) that clients must connect from in order to use the token.  If not
  provided, access is not restricted based on the IP address.  Both IPv4 and
  IPv6 are supported.

- ``perm_manage_tokens``:  If set to ``true``, the token can be used to
  authorize token management operations (as described in this chapter).

Additionally, you can configure an expiration policy with the following fields:

- ``max_age``:  Force token expiration when a certain time period has passed
  since its creation.  If ``null``, the token does not expire due to age.

- ``max_unused_period``:  Require that the token is used a least once within
  the given time period to prevent it from expiring.  If ``null``, the token
  does not expire due to it not being used.

If a field is provided but has invalid content, ``400 Bad Request`` is
returned, with error details in the body.


Modifying a Token
`````````````````

To modify a token, send a ``PATCH`` or ``PUT`` request to the
``auth/tokens/{id}/`` endpoint of the token you would like to modify::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "my new token"}'

The ID given in the URL is the ID of the token that will be modified.  Upon
success, the server will reply with ``200 OK``.

The token given in the ``Authorization`` header requires the
``perm_manage_tokens`` permission.  If permissions are insufficient, the
server will return ``403 Forbidden``.

``name`` and all other fields are optional.  The list of fields that can be
given is the same as when `Creating a Token`_.  If a field is provided but has
invalid content, ``400 Bad Request`` is returned, with error details in the
body.

**Note:**  As long as the ``perm_manage_tokens`` permission is in effect, it
is possible for a token to grant and revoke its own permissions.  However, if
the ``perm_manage_tokens`` permission is removed, the operation can only be
reversed by means of another token that has this permission.


Listing Tokens
``````````````

To retrieve a list of all known tokens, issue a ``GET`` request as follows::

    curl -X GET https://desec.io/api/v1/auth/tokens/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The server will respond with a list of token objects.  Up to 500 items are
returned at a time. If you have a larger number of tokens configured, the use
of :ref:`pagination` is required.


Retrieving a Specific Token
```````````````````````````

To retrieve information about a specific token, issue a ``GET`` request to the
token's endpoint::

    curl -X GET https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The response will contain a token object as described under `Token Field
Reference`_.  You can use it to check a token's properties, such as name,
timestamps of creation and last use, or permissions.

**Note:** The response does *not* contain the token value itself!


.. _delete-tokens:

Deleting a Token
````````````````

To delete an existing token by its ID via the token management endpoints, issue a
``DELETE`` request on the token's endpoint, replacing ``{id}`` with the
token ``id`` value::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

If you do not have the token UUID, but you do have the token value itself, you
can use the :ref:`log-out` endpoint to delete it.


Token Scoping: Domain Policies
``````````````````````````````
Tokens by default can be used to authorize arbitrary actions within the user's
account, including some administrative tasks and DNS operations on any domain.
As such, tokens are considered *privileged* when no further configuration is
done.
(This applies to v1 of the API and may change in a later version.)

Tokens can be *restricted* using Token Policies, which narrow down the scope
of influence for a given API token.
Using policies, the token's power can be limited in two ways:

1. the types of DNS operations that can be performed, such as :ref:`dynDNS
   updates <update-api>` or :ref:`general RRset management <manage-rrsets>`.

2. the set of domains on which these actions can be performed.

Policies can be configured on a per-domain basis.
Domains for which no explicit policy is configured are subject to the token's
default policy.
It is required to create such a default policy before any domain-specific
policies can be created.

Tokens with at least one policy are considered *restricted*, with their scope
explicitly limited to DNS record management.
They can perform neither :ref:`retrieve-account-information` nor
:ref:`domain-management` (such as domain creation or deletion).

**Please note:**  Token policies are *independent* of high-level token
permissions that can be assigned when `Creating a Token`_.
In particular, a restricted token that at the same time has the
``perm_manage_tokens`` permission is able to free itself from its
restrictions (see `Token Field Reference`_).


Token Domain Policy Field Reference
-----------------------------------

A JSON object representing a token domain policy has the following structure::

    {
        "domain": "example.com",
        "perm_dyndns": false,
        "perm_rrsets": true
    }

Field details:

``domain``
    :Access mode: read, write
    :Type: string or ``null``

    Domain name to which the policy applies.  ``null`` for the default policy.

``perm_dyndns``
    :Access mode: read, write
    :Type: boolean

    Indicates whether :ref:`dynDNS updates <update-api>` are allowed.
    Defaults to ``false``.

``perm_rrsets``
    :Access mode: read, write
    :Type: boolean

    Indicates whether :ref:`general RRset management <manage-rrsets>` is
    allowed.  Defaults to ``false``.


Token Domain Policy Management
------------------------------
Token Domain Policies are managed using the ``policies/domain/`` endpoint
under the token's URL.
Usage of this endpoint requires that the request's authorization token has the
``perm_manage_tokens`` flag.

Semantics, input validation, and error handling follow the same style as the
rest of the API, so is not documented in detail here.
For example, to retrieve a list of policies for a given token, issue a ``GET``
request as follows::

    curl -X GET https://desec.io/api/v1/auth/tokens/{id}/policies/domain/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The server will respond with a list of token domain policy objects.

To create the default policy, send a request like::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/policies/domain/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"domain": null}'

This will create a default policy.  Permission flags that are not given are
assumed to be ``false``.  To enable permissions, they have to be set to
``true`` explicitly.  As an example, let's create a policy that only allows
dynDNS updates for a specific domain::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/policies/domain/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"domain": "example.dedyn.io", "perm_dyndns": true}'

You can retrieve (``GET``), update (``PATCH``, ``PUT``), and remove
(``DELETE``) policies by appending their ``domain`` to the endpoint::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/{id}/policies/domain/{domain}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The default policy can be accessed using the special domain name ``default``
(``/api/v1/auth/tokens/{id}/policies/domain/default/``).

When modifying or deleting policies, the API enforces the default policy's
primacy:
You cannot create domain-specific policies without first creating a default
policy, and you cannot remove a default policy when other policies are still
in place.

During deletion of tokens, users, or domains, policies are cleaned up
automatically.  (It is not necessary to first remove policies manually.)

Security Considerations
```````````````````````

This section is for purely informational. Token length and encoding may change
in the future.

Any token is generated from 168 bits of randomness at the server and stored in
hashed format (PBKDF2-HMAC-SHA256). Guessing the token correctly or reversing
the hash is hence practically impossible.

The token value is represented by 28 characters using a URL-safe variant of
base64 encoding. It comprises only the characters ``A-Z``, ``a-z``, ``0-9``, ``-``,
and ``_``. (Base64 padding is not needed as the string length is a multiple of 4.)

Old versions of the API encoded 20-byte tokens in 40 characters with hexadecimal
representation. Such tokens are not issued anymore, but remain valid until
invalidated by the user.
