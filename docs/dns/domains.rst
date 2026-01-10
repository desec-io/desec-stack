.. _domain-management:

Domain Management
-----------------

Domain management is done through the ``/api/v1/domains/`` endpoint.  The
following sections describe how to create, list, modify, and delete domains
using JSON objects and how to export domain data in zonefile format.

All operations are subject to rate limiting.  For details, see
:ref:`rate-limits`.


.. _`domain object`:

Domain Field Reference
~~~~~~~~~~~~~~~~~~~~~~

A JSON object representing a domain has the following structure::

    {
        "created": "2018-09-18T16:36:16.510368Z",
        "delegation_checked": "2018-09-18T17:30:00.000000Z",
        "has_all_nameservers": true,
        "is_delegated": true,
        "is_registered": true,
        "is_secured": false,
        "keys": [
            {
                "dnskey": "257 3 13 WFRl60...",
                "ds": [
                    "6006 13 2 f34b75...",
                    "6006 13 4 2fdcf8..."
                ],
                "flags": 257,  # deprecated
                "keytype": "csk",  # deprecated
                "managed": true
            },
            ...
        ],
        "minimum_ttl": 3600,
        "name": "example.com",
        "published": "2018-09-18T17:21:38.348112Z",
        "touched": "2018-09-18T17:21:38.348112Z",
        "zonefile": "import-me.example A 127.0.0.1 ..."
    }

Field details:

``created``
    :Access mode: read-only

    Timestamp of domain creation, in ISO 8601 format (e.g.
    ``2013-01-29T12:34:56.000000Z``).

``delegation_checked``
    :Access mode: read-only

    Timestamp of the last delegation check. If no check has happened yet, this
    field is ``null``.

``has_all_nameservers``
    :Access mode: read-only

    ``true`` if the domain is delegated and all authoritative nameservers at the
    parent match deSEC. ``false`` indicates a partial delegation. ``null`` if no
    delegation information is available.

``is_delegated``
    :Access mode: read-only

    ``true`` if the domain is delegated to deSEC, ``false`` if only partially,
    ``null`` if delegation does not point to deSEC at all.

``is_registered``
    :Access mode: read-only

    ``true`` if the domain exists in the public DNS, ``false`` if it is not
    visible (yet), ``null`` if no check has been performed.

``is_secured``
    :Access mode: read-only

    ``true`` if DNSSEC is correctly configured and matches deSEC's keys,
    ``false`` if the DS records do not match, ``null`` if no DNSSEC data was
    found.

``keys``
    :Access mode: read-only

    Array with DNSSEC public key information.  Each entry contains ``DNSKEY``
    and ``DS`` record contents.  For delegation of DNSSEC-secured domains,
    the parent domain should publish the combined list of ``DS`` records.
    (This usually involves telling your registrar/registry about those
    records, and they will publish them for you.)

    Notes:

    - Keys are returned immediately after domain creation, and when retrieving
      a specific domain.  In contrast, when listing all domains, the ``keys``
      field is omitted for performance reasons.

    - The ``managed`` field differentiates keys managed by deSEC (``true``)
      from any additional keys the user may have added (``false``, see
      :ref:`DNSKEY caveat <DNSKEY caveat>`).

    - ``DS`` values are calculated for each applicable key by applying hash
      algorithms 2 (SHA-256) and 4 (SHA-384), respectively.
      For keys not suitable for delegation (indicated by the first field
      containing an even number, such as ``256``), the ``ds`` field is ``[]``.
      The selection of hash algorithms may change as best practices evolve.

``minimum_ttl``
    :Access mode: read-only

    Smallest TTL that can be used in an :ref:`RRset <RRset object>`. The value
    is set automatically by the server.

    If you would like to use lower TTL values, you can apply for an exception
    by contacting support.  We reserve the right to reject applications at our
    discretion.

``name``
    :Access mode: read, write-once (upon domain creation)

    Domain name.  Restrictions on what is a valid domain name apply on a
    per-user basis.  In general, a domain name consists of lowercase alphanumeric
    characters as well as hyphens ``-`` and underscores ``_`` (except at the
    beginning of the name).  The maximum length is 191.

    Internationalized domain names (IDN) currently are supported through their
    Punycode representation only (labels beginning with ``xn--``).  Converters
    are available on the net, for example at https://www.punycoder.com/.

``published``
    :Access mode: read-only

    Timestamp of when the domain's DNS records have last been published,
    in ISO 8601 format (e.g. ``2013-01-29T12:34:56.000000Z``).

    As we publish record modifications immediately, this indicates the
    point in time of the last successful write request to a domain's
    ``rrsets/`` endpoint.

``touched``
    :Access mode: read-only

    Timestamp of when the domain's DNS records have last been touched. Equal to
    the maximum of the domain's ``published`` field and all :ref:`RRset <RRset
    object>` ``touched`` values.

    This usually is the same as ``published``, unless there have been RRset
    write operations that did not trigger publication, such as rewriting an
    RRset with identical values.

``zonefile``
    :Access mode: write-only, no read

    Optionally, includes a string in zonefile format with record data to be
    imported during domain creation.

    Note that not everything given in the zonefile will be imported. Record
    types that are :ref:`automatically managed by the deSEC API <automatic
    types>` such as RRSIG, CDNSKEY, CDS, etc. will be silently ignored.
    Records with names that fall outside of the domain that is created will
    also be silently ignored.

    Also, NS record at the apex and any DNSKEY records will be
    silently ignored; instead, NS records pointing to deSEC's name servers
    and DNSKEY records for freshly generated keys will be created.

    :ref:`Record types that are not supported <unsupported types>` by the API
    will raise an error, as will records with invalid content.
    If an error occurs during the import of the zonefile, the domain will not
    be created.


Creating a Domain
~~~~~~~~~~~~~~~~~

To create a new domain, issue a ``POST`` request to the ``/api/v1/domains/``
endpoint, like this::

    curl https://desec.io/api/v1/domains/ \
        --header "Authorization: Token {secret}" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "example.com"}'

This operation requires the ``perm_create_domain`` permission on the token.
Only the ``name`` field is mandatory.

Upon success, the response status code will be ``201 Created``, with the
domain object contained in the response body.  If an improper request was
sent, ``400 Bad Request`` is returned.  This can happen when the request
payload was malformed, or when the requested domain name is unavailable
(because it conflicts with another user's zone) or invalid (due to policy, see
below).

If you have reached the maximum number of domains for your account, the API
responds with ``403 Forbidden``.  If you find yourself affected by this limit
although you have a legitimate use case, please contact our support.

If you have reached the per-account limit for domains delegated without DNSSEC,
the API responds with ``403 Forbidden`` when creating additional domains.
Secure an existing domain by adding the DS records shown in the UI or API, then
try again.

If the per-account limit is set to ``0``, domain creation is disabled.
If the limit is ``null``, there is no restriction based on DNSSEC status.

Restrictions on what is a valid domain name apply.  In particular, domains
listed on the `Public Suffix List`_ such as ``co.uk`` cannot be registered.
(If you operate a public suffix and would like to host it with deSEC, that's
certainly possible; please contact support.) Also, domains ending with
``.internal`` cannot be registered.

.. _Public Suffix List: https://publicsuffix.org/

Furthermore, we may impose other restrictions on a per-user basis if necessary
to enforce our `Terms of Use`_.

.. _Terms of Use: https://desec.io/terms


Listing Domains
~~~~~~~~~~~~~~~

The ``/api/v1/domains/`` endpoint responds to ``GET`` requests with an array of
`domain object`_\ s. For example, you may issue the following command::

    curl https://desec.io/api/v1/domains/ \
        --header "Authorization: Token {secret}"

to retrieve an overview of the domains you own.  Domains are returned in
reverse chronological order of their creation, and DNSSEC keys are omitted.

The response status code in case of success is ``200 OK``.  This is true also
if you do not own any domains; in this case, the response body will be an empty
JSON array.

Up to 500 items are returned at a time.  If you have a larger number of
domains configured, the use of :ref:`pagination` is required.


Delegation Status Checks
~~~~~~~~~~~~~~~~~~~~~~~~

deSEC periodically checks how your domain is published in the public DNS.
The results are stored in the delegation status fields described above
(``delegation_checked``, ``is_registered``, ``is_delegated``,
``has_all_nameservers``, ``is_secured``).

The checks use public resolvers to determine:

- whether the domain exists in the public DNS (registered),
- whether the delegation points to deSEC name servers,
- whether DNSSEC is correctly configured for your domain.

The API does not change or delete domains based on these checks. However, if
you have at least one domain delegated to deSEC without DNSSEC, you cannot
create additional domains until that domain is secured.

If you need details about a domain's current status, request the domain via
``GET /api/v1/domains/{name}/`` or list domains via ``GET /api/v1/domains/`` and
inspect the delegation fields.


Retrieving a Specific Domain
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve a domain with a specific name, issue a ``GET`` request with the
``name`` appended to the ``domains/`` endpoint, like this::

    curl https://desec.io/api/v1/domains/{name}/ \
        --header "Authorization: Token {secret}"

This will return only one domain (i.e., the response is not a JSON array).

If you own a domain with that name, the API responds with ``200 OK`` and
returns the domain object in the response body.  Otherwise, the return status
code is ``404 Not Found``.


Identifying the Responsible Domain for a DNS Name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have several domains which share a DNS suffix (i.e. one domain is a
parent of the other), it is sometimes necessary to find out which domain is
responsible for a given DNS name.  (In DNS terminology, the responsible domain
is also called the "authoritative zone".)

The responsible domain for a given DNS query name (``qname``) can be retrieved
by applying a filter on the endpoint used for `Listing Domains`_, like so::

    curl https://desec.io/api/v1/domains/?owns_qname={qname} \
        --header "Authorization: Token {secret}"

If your account has a domain that is responsible for the name ``qname``, the
API returns a JSON array containing only that domain object in the response
body.  Otherwise, the JSON array will be empty.

One use case of this is when requesting TLS certificates using the DNS
challenge mechanism, which requires placing a ``TXT`` record at a certain name
within the responsible domain.

Example
```````
Let's say you have the domains ``example.net``, ``dev.example.net`` and
``git.dev.example.net``, and you would like to request a certificate for the
TLS server name ``www.dev.example.net``.  In this case, the ``TXT`` record
needs to be created with the name ``_acme-challenge.www.dev.example.net``.

This DNS name belongs to the ``dev.example.net`` domain, and the record needs
to be created under that domain using the ``subname`` value
``_acme-challenge.www`` (see :ref:`creating-an-rrset`).

If ``dev.example.net`` was not configured as a domain in its own right, the
responsible domain would instead be the parent domain ``example.net``.  In
this case, the record would have to be configured there, with a ``subname``
value of ``_acme-challenge.www.dev``.

Finally, when requesting a certificate for ``git.dev.example.net``, the
responsible domain for the corresponding DNS record is the one with this name,
and ``subname`` would just be ``_acme-challenge``.

The above API request helps you answer this kind of question.


.. _exporting-a-domain:

Exporting a Domain as Zonefile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To export domain data in zonefile format, send a ``GET`` request to the
``zonefile`` endpoint of this domain, i.e. to ``/domains/{name}/zonefile/``::

    curl https://desec.io/api/v1/domains/{name}/zonefile/ \
        --header "Authorization: Token {secret}"

Note that this will return a plain-text zonefile format without JSON formatting
that includes all domain data except for DNSSEC-specific record types, e.g.::

    ; Zonefile for example.com exported from desec.io at 2022-08-26 16:03:18.258961+00:00
    example.com.	1234	IN	NS	ns1.example.com.
    example.com.	1234	IN	NS	ns2.example.com.
    example.com.	300	IN	SOA	get.desec.io. get.desec.io. 2022082602 86400 3600 2419200 3600


.. _deleting-a-domain:

Deleting a Domain
~~~~~~~~~~~~~~~~~

To delete a domain, send a ``DELETE`` request to the endpoint representing the
domain. This operation requires the ``perm_delete_domain`` permission on the
token, and no conflicting token scoping policies.

Upon success or if the domain did not exist in your account, the response
status code is ``204 No Content``.
