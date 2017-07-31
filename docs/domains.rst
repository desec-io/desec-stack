Domain Management
-----------------

Domain management is done through the ``/api/v1/domains/`` endpoint.  The
following sections describe how to create, list, modify, and delete domains
using JSON objects.  The structure of the JSON objects is detailed in the next
section.


.. _`domain object`:

Domain Field Reference
~~~~~~~~~~~~~~~~~~~~~~

A JSON object representing a domain has the following structure::

    {
        "name": "example.com",
        "owner": "admin@example.com",
        "keys": [
            {
                "dnskey": "257 3 13 WFRl60...",
                "ds": [
                    "6006 13 1 8581e9...",
                    "6006 13 2 f34b75...",
                    "6006 13 3 dfb325...",
                    "6006 13 4 2fdcf8..."
                ],
                "flags": 257,
                "keytype": "csk"
            },
            ...
        ],
        "arecord": "192.0.2.1",             # or null
        "aaaarecord": "2001:db8::deec:1",   # or null
        "acme_challenge": ""
    }

Field details:

``aaaarecord``
    :Access mode: read, write
    :Notice: this field is deprecated

    String with an IPv6 address that will be written to the ``AAAA`` RRset of
    the zone apex, or ``null``.  If ``null``, the RRset is removed.

    This was originally introduced to set an IPv6 address for deSEC's dynamic
    DNS service dedyn.io.  However, it has some drawbacks (redundancy with
    `Modifying an RRset`_ as well as inability to set multiple addresses).

    *Do not rely on this field; it may be removed in the future.*

``acme_challenge``
    :Access mode: read, write
    :Notice: this field is deprecated

    String to be written to the ``TXT`` RRset of ``_acme-challenge.{name}``.
    To set an empty challenge, use ``""``.  The maximum length is 255.

    This was originally introduced to set an ACME challenge to allow obtaining
    certificates from Let's Encrypt using deSEC's dynamic DNS service
    dedyn.io.  However, it is redundant with `Modifying an RRset`_.

    *Do not rely on this field; it may be removed in the future.*

``arecord``
    :Access mode: read, write
    :Notice: this field is deprecated

    String with an IPv4 address that will be written to the ``A`` RRset of the
    zone apex, or ``null``.  If ``null``, the RRset is removed.

    This was originally introduced to set an IPv4 address for deSEC's dynamic
    DNS service dedyn.io.  However, it has some drawbacks (redundancy with
    `Modifying an RRset`_ as well as inability to set multiple addresses).

    *Do not rely on this field; it may be removed in the future.*

``keys``
    :Access mode: read-only

    Array with DNSSEC key information.  Each entry contains ``DNSKEY`` and
    ``DS`` record contents (the latter being computed from the former), and
    some extra information.  For delegation of DNSSEC-secured domains, the
    domain registry needs to publish these ``DS`` records.

    Notes:

    - Newly created domains are assigned a key after a short while (usually
      around one minute).  Until then, this field is empty.

    - The contents of this field are generated from PowerDNS' ``cryptokeys``
      endpoint, see https://doc.powerdns.com/md/httpapi/api_spec/#cryptokeys.
      We look at each active ``cryptokey_resource`` (``active`` is true) and
      then use the ``dnskey``, ``ds``, ``flags``, and ``keytype`` fields.

``name``
    :Access mode: read, write-once (upon domain creation)

    Domain name.  Restrictions on what is a valid domain name apply on a
    per-user basis.  In general, a domain name consists of alphanumeric
    characters as well as hyphens ``-`` and underscores ``_`` (except at the
    beginning of the name).  The maximum length is 191.

``owner``
    :Access mode: read-only

    Email address of the user owning the domain.


Creating a Domain
~~~~~~~~~~~~~~~~~

To create a new domain, issue a ``POST`` request to the ``/api/v1/domains/``
endpoint, like this::

    http POST \
        https://desec.io/api/v1/domains/ \
        Authorization:"Token {token}" \
        name:='"example.com"'

Only the ``name`` field is mandatory; ``arecord``, ``acme_challenge``, and
``aaaarecord`` are optional and deprecated.

Upon success, the response status code will be ``201 Created``, with the
domain object contained in the response body.  ``400 Bad Request`` is returned
if the request contained malformed data such as syntactically invalid field
contents for ``arecord`` or ``aaaarecord``.  If the object could not be
created although the request was wellformed, the API responds with ``403
Forbidden`` if the maximum number of domains for this user has been reached,
and with ``409 Conflict`` otherwise.  This can happen, for example, if there
already is a domain with the same name or if the domain name is considered
invalid for policy reasons.

Restrictions on what is a valid domain name apply on a per-user basis.  The
response body *may* provide further, human-readable information on the policy
violation that occurred.


Listing Domains
~~~~~~~~~~~~~~~

The ``/api/v1/domains/`` endpoint reponds to ``GET`` requests with an array of
`domain object`_\ s. For example, you may issue the following command::

    http GET \
        https://desec.io/api/v1/domains/ \
        Authorization:"Token {token}"

to retrieve an overview of the domains you own.

The response status code is ``200 OK``.  This is true also if you do not own
any domains; in this case, the response body will be an empty JSON array.


Retrieving a Specific Domain
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve a domain with a specific name, issue a ``GET`` request with the
``name`` appended to the ``domains/`` endpoint, like this::

    http GET \
        https://desec.io/api/v1/domains/{name}/ \
        Authorization:"Token {token}"

This will return only one domain (i.e., the response is not a JSON array).

If you own a domain with that name, the API responds with ``200 OK`` and
returns the domain object in the reponse body.  Otherwise, the return status
code is ``404 Not Found``.


Modifying a Domain (deprecated)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To modify a domain, use the endpoint that you would also use to retrieve that
specific domain.  The API allows changing the values of the ``arecord``,
``acme_challenge``, and ``aaaarecord`` fields using the ``PATCH`` method.
Only the field(s) provided in the request will be modified, with everything
else untouched.  Examples::

    # Set AAAA record
    http PATCH \
        https://desec.io/api/v1/domains/{name}/ \
        Authorization:"Token {token}" \
        aaaarecord:='"2001:db8::deec:1"'

    # Remove A record and set empty ACME challenge
    http PATCH \
        https://desec.io/api/v1/domains/{name}/ \
        Authorization:"Token {token}" \
        acme_challenge:='""' arecord:='null'

If the domain was updated successfully, the response status code is ``200 OK``
and the updated domain object is returned in the response body.  In case of
malformed request data such as syntactically invalid field contents for
``arecord`` or ``aaaarecord``, ``400 Bad Request`` is returned.  If the domain
does not exist or you don't own it, the status code is ``404 Not Found``.


Deleting a Domain
~~~~~~~~~~~~~~~~~

To delete a domain, send a ``DELETE`` request to the endpoint representing the
domain.  Upon success or if the domain did not exist or was not yours in the
first place, the response status code is ``204 No Content``.
