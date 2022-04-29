.. _domain-management:

Domain Management
-----------------

Domain management is done through the ``/api/v1/domains/`` endpoint.  The
following sections describe how to create, list, modify, and delete domains
using JSON objects.

All operations are subject to rate limiting.  For details, see
:ref:`rate-limits`.


.. _`domain object`:

Domain Field Reference
~~~~~~~~~~~~~~~~~~~~~~

A JSON object representing a domain has the following structure::

    {
        "created": "2018-09-18T16:36:16.510368Z",
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
        "touched": "2018-09-18T17:21:38.348112Z"
    }

Field details:

``created``
    :Access mode: read-only

    Timestamp of domain creation, in ISO 8601 format (e.g.
    ``2013-01-29T12:34:56.000000Z``).

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


Creating a Domain
~~~~~~~~~~~~~~~~~

To create a new domain, issue a ``POST`` request to the ``/api/v1/domains/``
endpoint, like this::

    curl -X POST https://desec.io/api/v1/domains/ \
        --header "Authorization: Token {token}" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "example.com"}'

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

    curl -X GET https://desec.io/api/v1/domains/ \
        --header "Authorization: Token {token}"

to retrieve an overview of the domains you own.  Domains are returned in
reverse chronological order of their creation, and DNSSEC keys are omitted.

The response status code in case of success is ``200 OK``.  This is true also
if you do not own any domains; in this case, the response body will be an empty
JSON array.

Up to 500 items are returned at a time.  If you have a larger number of
domains configured, the use of :ref:`pagination` is required.


Retrieving a Specific Domain
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve a domain with a specific name, issue a ``GET`` request with the
``name`` appended to the ``domains/`` endpoint, like this::

    curl -X GET https://desec.io/api/v1/domains/{name}/ \
        --header "Authorization: Token {token}"

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

    curl -X GET https://desec.io/api/v1/domains/?owns_qname={qname} \
        --header "Authorization: Token {token}"

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


.. _deleting-a-domain:

Deleting a Domain
~~~~~~~~~~~~~~~~~

To delete a domain, send a ``DELETE`` request to the endpoint representing the
domain.  Upon success or if the domain did not exist in your account, the
response status code is ``204 No Content``.
