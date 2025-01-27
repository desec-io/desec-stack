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
        "id": "3a6b94b5-d20e-40bd-a7cc-521f5c79fab3",
        "created": "2018-09-06T09:08:43.762697Z",
        "last_used": null,
        "owner": "youremailaddress@example.com"",
        "user_override": null,
        "max_age": "365 00:00:00",
        "max_unused_period": null,
        "name": "my new token",
        "perm_create_domain": false,
        "perm_delete_domain": false,
        "perm_manage_tokens": false,
        "allowed_subnets": [
            "0.0.0.0/0",
            "::/0"
        ],
        "auto_policy": false,
        "token": "4pnk7u-NHvrEkFzrhFDRTjGFyX_S"
    }

Field details:

``allowed_subnets``
    :Access mode: read, write
    :Type: Array of IPs or IP subnets

    Exhaustive list of IP addresses or subnets clients must connect from in
    order to successfully authenticate with the token.  Both IPv4 and IPv6 are
    supported.  Defaults to ``0.0.0.0/0, ::/0`` (no restriction).

``auto_policy``
    :Access mode: read, write
    :Type: boolean

    When using this token to create a domain, automatically configure a
    permissive scoping policy for it (``perm_write=true``).  Requires a
    restrictive default policy (``perm_write=false``), which is created
    automatically when setting this flag.  Cannot be set to true if a
    permissive default policy exists.  For details, see
    :ref:`token scoping policies`.

``created``
    :Access mode: read-only
    :Type: timestamp

    Timestamp of token creation, in ISO 8601 format (e.g.
    ``2018-09-06T09:08:43.762697Z``).

``id``
    :Access mode: read-only
    :Type: UUID

    Token ID, used for identification only (e.g. when deleting a token). This
    is *not* the token's secret value.

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

``perm_create_domain``
    :Access mode: read, write
    :Type: boolean

    Permission to create a new domain.

``owner``
    :Access mode: read
    :Type: string

    Email address associated with the deSEC account that created the token.

``perm_delete_domain``
    :Access mode: read, write
    :Type: boolean

    Permission to delete a domain. When using :ref:`token scoping policies`,
    deleting a domain also requires write permission on all its RRsets.

``perm_manage_tokens``
    :Access mode: read, write
    :Type: boolean

    Permission to manage tokens (this one and also all others).  A token which
    does not have this flag set cannot access the ``auth/tokens/`` endpoints.

``token``
    :Access mode: read-once
    :Type: string

    The token's secret value that is used to authenticate API requests.  It is only
    returned once, upon creation of the token.  The secret value of an existing token
    cannot be recovered (we store it in irreversibly hashed form).  For
    security details, see `Security Considerations`_.

``user_override``
    :Access mode: read
    :Type: string or ``null``

    Email address associated with the deSEC account to which actions performed
    with this token will pertain (default: ``null``).
    In other words, if this field is set, then the token will not authenticate
    as the ``owner`` user, but as the ``user_override`` user.
    For details, see `User Override`_.


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
        "owner": "youremailaddress@example.com"",
        "user_override": null,
        "name": "my new token",
        "perm_create_domain": false,
        "perm_delete_domain": false,
        "perm_manage_tokens": false,
        "allowed_subnets": [
            "0.0.0.0/0",
            "::/0"
        ],
        "auto_policy": false,
        "token": "4pnk7u-NHvrEkFzrhFDRTjGFyX_S"
    }

The new token will, by default, possess fewer permissions than a login token.
In particular, the ``perm_manage_tokens`` flag will not be set, so that the
new token cannot be used to retrieve, modify, or delete any tokens (including
itself).

Similarly, tokens by default cannot create or delete any domains (although they
can manage DNS records of existing domains, unless restricted through
:ref:`token scoping policies`). Note that it is always possible to use the
:ref:`log-out` endpoint to delete a token.

If you require tokens with extra permissions, you can provide the desired
configuration during creation:

- ``allowed_subnets``:  In this field, you can list the IP addresses (or
  subnets) that clients must connect from in order to use the token.  If not
  provided, access is not restricted based on the IP address.  Both IPv4 and
  IPv6 are supported.

- ``perm_create_domain``:  If set to ``true``, the token can be used to
  create domains.

- ``perm_delete_domain``:  If set to ``true``, the token can be used to
  delete domains.

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

    curl -X PATCH https://desec.io/api/v1/auth/tokens/{id}/ \
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

**Note:** The response does *not* contain the token's secret value!


.. _delete-tokens:

Deleting a Token
````````````````

To delete an existing token by its ID via the token management endpoints, issue a
``DELETE`` request on the token's endpoint, replacing ``{id}`` with the
token ``id`` value::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/{id}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

If you do not have the token ID, but you do have the token secret, you
can use the :ref:`log-out` endpoint to delete it.


.. _`token scoping policies`:

Token Scoping: Policies
```````````````````````

Tokens by default can be used to authorize arbitrary actions within the user's
account, including DNS operations on any domain and some administrative tasks.
As such, tokens are considered *privileged* when no further configuration is
done.
(This applies to v1 of the API and may change in a later version.)

Tokens can be *restricted* using Token Policies, which narrow down the scope
of influence for a given API token.
Using policies, the token's power can be limited in two ways:

1. the type of access control (*allow-by-default* or *deny-by-default)* for DNS
   write operations, such as :ref:`dynDNS updates <update-api>` or
   :ref:`general RRset management <manage-rrsets>`;

2. explicit access control for specific RRsets through the policy's ``domain``,
   ``subname``, and ``type`` fields.

All tokens can, regardless of their policy configuration, read any RRset (for
all domains in the account).  This is because essentially the same information
is also available through the DNS.  Note that the API in addition exposes some
metadata, such as the RRset's ``created`` or ``touched`` timestamps.

Write permissions can be configured on a per-RRset basis. When attempting to
manipulate an RRset, the applicable policy is identified by matching the RRset
against existing policies in the following order:

+----------+------------+-------------+----------+
| Priority | ``domain`` | ``subname`` | ``type`` |
+==========+============+=============+==========+
| 1        | match      | match       | match    |
+----------+------------+-------------+----------+
| 2        | match      | match       | *null*   |
+----------+------------+-------------+----------+
| 3        | match      | *null*      | match    |
+----------+------------+-------------+----------+
| 4        | match      | *null*      | *null*   |
+----------+------------+-------------+----------+
| 5        | *null*     | match       | match    |
+----------+------------+-------------+----------+
| 6        | *null*     | match       | *null*   |
+----------+------------+-------------+----------+
| 7        | *null*     | *null*      | match    |
+----------+------------+-------------+----------+
| 8        | *null*     | *null*      | *null*   |
+----------+------------+-------------+----------+

Taking the (``domain``, ``subname``, ``type``) tuple as a path, this can be
considered a longest-prefix match algorithm. Wildcards are not expanded and
match only RRsets with an identical wildcard ``subname``.

RRsets for which no more specific policy is configured are eventually caught by
the token's default policy.  It is therefore required to create such a default
policy before any more specific policies can be created on a given token.
A domain-wide permissive policy can be configured automatically during domain
creation by setting the token's ``auto_policy`` flag.

Tokens with at least one policy are considered *restricted*, with their DNS
record management capabilities limited as per policy configuration.
Whether :ref:`domain-management` is allowed depends on the
``perm_create_domain`` and ``perm_delete_domain`` permissions.
Restricted tokens cannot be used to perform other actions (e.g.,
:ref:`retrieve-account-information`).

**Note:**  Token policies are *independent* of high-level token permissions
that can be assigned when `Creating a Token`_.
In particular, a restricted token that at the same time has the
``perm_manage_tokens`` permission is able to free itself from its
restrictions (see `Token Field Reference`_).


Token Policy Field Reference
----------------------------

A JSON object representing a token policy has the following structure::

    {
        "id": "7aed3f71-bc81-4f7e-90ae-8f0df0d1c211",
        "domain": "example.com",
        "subname": null,
        "type": null,
        "perm_write": true
    }

Field details:

``id``
    :Access mode: read-only
    :Type: UUID

    Token policy ID, used for identification only (e.g. when modifying a
    policy). (Not to be confused with the token's ID.)

``domain``
    :Access mode: read, write
    :Type: string or ``null``

    Domain name to which the policy applies.  ``null`` for the default policy.

``subname``
    :Access mode: read, write
    :Type: string or ``null``

    Subname to which the policy applies.  ``null`` for the default policy.

``type``
    :Access mode: read, write
    :Type: string or ``null``

    Record type to which the policy applies.  ``null`` for the default policy.

``perm_write``
    :Access mode: read, write
    :Type: boolean

    Indicates write permission for the RRset specified by (``domain``,
    ``subname``, ``type``) when using the :ref:`general RRset management
    <manage-rrsets>` or :ref:`dynDNS <update-api>` interface.  Defaults to
    ``false``.


Token Policy Management
-----------------------
Token Policies are managed using the ``policies/rrsets/`` endpoint under the
token's URL.
Usage of this endpoint requires that the request's authorization token has the
``perm_manage_tokens`` flag.

Semantics, input validation, and error handling follow the same style as the
rest of the API, so is not documented in detail here.
For example, to retrieve a list of policies for a given token, issue a ``GET``
request as follows::

    curl -X GET https://desec.io/api/v1/auth/tokens/{id}/policies/rrsets/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

The server will respond with a list of token policy objects.

To create the default policy, send a request like::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/policies/rrsets/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"domain": null, "subname": null, "type": null}'

This will create a default policy.  If the ``perm_write`` permission flag is
not given, it is assumed to be ``false``.

As an example, let's create a policy that only allows manipulating all A
records for a specific domain::

    curl -X POST https://desec.io/api/v1/auth/tokens/{id}/policies/rrsets/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"domain": "example.dedyn.io", "subname": null, "type": "A", "perm_write": true}'

**Tip:** To authorize dual-stack dynDNS updates, create two policies (for
access to the A and AAAA RRsets, respectively).

You can retrieve (``GET``), update (``PATCH``, ``PUT``), and remove
(``DELETE``) policies by appending their ``id`` to the endpoint::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/{token.id}/policies/rrsets/{policy.id}/ \
        --header "Authorization: Token mu4W4MHuSc0Hy-GD1h_dnKuZBond"

When modifying or deleting policies, the API enforces the default policy's
primacy:
You cannot create specific policies without first creating a default policy,
and you cannot remove a default policy when other policies are still in place.

During deletion of tokens, users, or domains, policies are cleaned up
automatically.


.. _`user-override`:

User Override
`````````````
One user can authorize another such that the latter can use their token to
perform actions in the name of the former.
For example, Alice can authorize Bob to use his (Bob's) token to act within her
(Alice's) account.

To this end, the email address associated with Alice's account needs to be set
in the ``user_override`` field of Bob's token.
After this, the token is called an "override token", and said to be "bound" to
the user given in the ``user_override`` field.
(Note that at this time, this feature is under development, and write access to
this field is not available.)

This construction allows Bob to act in Alice's name without requiring Alice to
share any secrets with Bob. (Bob can use his own secret token.)

Override tokens can access any domains in the target account, unless the token
has at least one policy configured.
In this case, visibility is restricted to domains for which a policy exists.
(This implies read permissions for domains listed with ``perm_write: false``.)

This feature is particularly useful when combined with the
``perm_create_domain`` and ``perm_delete_domain`` permissions, as well as the
``auto_policy`` flag:
In this case, Bob will be able to create, manage (due to ``auto_policy``) and
delete domains in Alice's account, without being able to see or modify other
domains (or even tokens) that Alice might have in her account.

When listing tokens, the configuration of override tokens is visible to both
their owner and the user listed in the ``user_override`` field.
To discern which tokens are (or are not) override tokens, associated email
addresses are listed in both the ``owner`` and ``user_override`` fields.
Note that as a result, both parties can observe when either deSEC account email
address changes.

Only the override user (not the token owner) can manage an override token,
including changing its name or permissions.
Token owners therefore should not rely on the name field for telling tokens
apart.
Further, only API tokens without the ``perm_manage_tokens`` permission are
eligible to become override tokens. (This is to prevent Bob from managing
Alice's tokens.)
However, both the owner and the override user can delete an override token.

Once ``user_override`` has been set, the binding of the token to the target
account is permanent. In particular, the binding will not be removed when the
associated account is deleted; instead, the override token will be silently
deleted.
(Example: If Bob owns an override token for Alice's account and she deletes her
account, then Bob's token will be deleted.)

In effect, there are two types of tokens: One that acts as the account that
owns it, and another that acts as a specific account that the token owner has
been authorized to act on behalf of. Once an override token has been authorized
to act on behalf of another user, it cannot be re-authorized to act on behalf
of a different user (including of its owner).

If you have ideas how this feature could be improved, please send us an email.
One question we're interested in is whether we should notify Bob (how?) about
the deletion of his override token when Alice deletes her account.


Security Considerations
```````````````````````

This section is for purely informational. Token length and encoding may change
in the future.

Any token secret is generated from 164 bits of randomness at the server and
stored in hashed format (PBKDF2-HMAC-SHA256).
Guessing the secret correctly or reversing the hash is considered practically
impossible.

The token's secret value is represented by 28 characters using a URL-safe
base58 encoding.
It is based on a case-sensitive alphanumeric alphabet excluding the characters
``lIO0`` (hence comprising only the symbols ``a-k``, ``m-z``, ``A-H``,
``J-N``, ``P-Z``, and ``1-9``).
This encoding is optimized for maximum clarity and usability:
Exclusion of certain letters minimizes visual ambiguity, while the restriction
to alphanumeric symbols allows easy selection (double-click) and input, and
helps avoid line breaks during display.

Before December 2022, tokens encoded a 21-byte secret using a URL-safe variant
of base64 encoding, comprising of the 28 characters ``A-Z``, ``a-z``, ``0-9``,
``-``, and ``_``.
(Base64 padding was not needed as the string length is a multiple of 4.)

Before September 2018, tokens encoded a 20-byte secret using 40 hexadecimal
characters.

Legacy tokens are not issued anymore, but remain valid until invalidated by
the user.
