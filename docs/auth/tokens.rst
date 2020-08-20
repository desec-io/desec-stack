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

``last_used``
    :Access mode: read-only
    :Type: timestamp (nullable)

    Timestamp of when the token was last successfully authenticated, or
    ``null`` if the token has never been used.

    In most cases, this corresponds to the last time when an API operation
    was performed using this token.  However, if the operation was not
    executed because it was found that the token did not have sufficient
    permission, this field will still be updated.

``name``
    :Access mode: read, write
    :Type: string

    Token name.  It is meant for user reference only and carries no
    operational meaning.  If omitted, the empty string is assumed.

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
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond" \
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

If a field is provided but has invalid content, ``400 Bad Request`` is
returned, with error details in the body.


Modifying a Token
`````````````````

To modify a token, send a ``PATCH`` or ``PUT`` request to the
``auth/tokens/{id}/`` endpoint of the token you would like to modify::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond" \
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

To retrieve a list of currently valid tokens, issue a ``GET`` request as
follows::

    curl -X GET https://desec.io/api/v1/auth/tokens/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will respond with a list of token objects.  Up to 500 items are
returned at a time. If you have a larger number of tokens configured, the use
of :ref:`pagination` is required.


Retrieving a Specific Token
```````````````````````````

To retrieve a list of currently valid tokens, issue a ``GET`` request to the
token's endpoint::

    curl -X GET https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

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
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

If you do not have the token UUID, but you do have the token value itself, you
can use the :ref:`log-out` endpoint to delete it.


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
