.. _manage-tokens:

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
        "token": "4pnk7u-NHvrEkFzrhFDRTjGFyX_S",
        "name": "my new token"
    }


.. _delete-tokens:

Delete Tokens
`````````````

To delete an existing token by its ID via the token management endpoints, issue a
``DELETE`` request on the token's endpoint, replacing ``:id`` with the
token ``id`` value::

    curl -X DELETE https://desec.io/api/v1/auth/tokens/:id/ \
        --header "Authorization: Token mu4W4MHuSc0HyrGD1h/dnKuZBond"

The server will reply with ``204 No Content``, even if the token was not found.

If you do not have the token UUID, but you do have the token value itself, you
can use the :ref:`log-out` endpoint to delete it.

Note that, for now, all tokens have equal power -- every token can authorize
any action. We are planning to implement scoped tokens in the future.


Security Considerations
```````````````````````

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
