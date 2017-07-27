Retrieving and Manipulating DNS Information
-------------------------------------------

All DNS information is composed of so-called *Resource Record Sets*
(*RRsets*).  An RRset is the set of all Resource Records of a given record
type for a given name.  For example, the name ``example.com`` may have an
RRset of type ``A``, denoting the set of IPv4 addresses associatd with this
name.  In the traditional Bind zone file format, the RRset would be written
as::

    <name>  IN  A 127.0.0.1
    <name>  IN  A 127.0.0.2
    ...

Each of these lines is a Resource Record, and together they form an RRset.

The basic units accessible through the API are RRsets, each represented by a
JSON object.  The object structure is detailed in the next section.

The relevant endpoints all reside under ``/api/v1/domains/{domain}/rrsets/``,
where ``{domain}`` is the name of a domain you own.  When operating on domains
that don't exist or you don't own, the API responds with a ``404 Not Found``
status code.  For a quick overview of the available endpoints, methods, and
operations, see `Endpoint Reference`_.


.. _`RRset object`:

RRset Field Reference
~~~~~~~~~~~~~~~~~~~~~

A JSON object representing an RRset has the following structure::

    {
        "domain": "example.com",
        "subname": "www",
        "name": "www.example.com.",
        "type": "A",
        "records": [
            "127.0.0.1",
            "127.0.0.2"
        ],
        "ttl": 3600
    }

Field details:

``domain``
    :Access mode: read-only

    Name of the zone to which the RRset belongs.

    Note that the zone name does not follow immediately from the RRset name.
    For example, the ``com`` zone contains an RRset of type ``NS`` for the
    name ``example.com.``, in order to set up the delegation to
    ``example.com``'s DNS operator.  The DNS operator's nameserver again
    has a similar ``NS`` RRset which, this time however, belongs to the
    ``example.com`` zone.

``name``
    :Access mode: read-only

    The full DNS name of the RRset.  If ``subname`` is empty, this is equal to
    ``{domain}.``, otherwise it is equal to ``{subname}.{domain}.``.

``records``
    :Access mode: read, write

    Array of record content strings.  The maximum number of array elements is
    4091, and the maximum length of the array is 64,000 (after JSON encoding).
    Note the `caveat on the priority field`_.

``subname``
    :Access mode: read, write-once (upon RRset creation)

    Subdomain string which, together with ``domain``, defines the RRset name.
    Typical examples are ``www`` or ``_443._tcp``.  In general, a subname
    consists of alphanumeric characters as well as hyphens ``-``, underscores
    ``_``, dots ``.``, and slashes ``/``.  Wildcard name components are
    denoted by ``*``; this is allowed only once at the beginning of the name
    (see RFC 4592 for details).  The maximum length is 178.  Further
    restrictions may apply on a per-user basis.

    If a ``subname`` contains slashes ``/`` and you are using it in the URL
    path (e.g. when `retrieving a specific RRset`_), it is required to escape
    them by replacing them with ``=2F``, to resolve the ambiguity that
    otherwise arises.  (This escape mechanism does not apply to query strings
    or inside JSON documents.)

``ttl``
    :Access mode: read, write

    TTL (time-to-live) value, which dictates for how long resolvers may cache
    this RRset, measured in seconds.  Only positive integer values are allowed.
    Additional restrictions may apply.

``type``
    :Access mode: read, write-once (upon RRset creation)

    RRset type (uppercase).  We support all `RRset types supported by
    PowerDNS`_, with the exception of DNSSEC-related types (the backend
    automagically takes care of setting those records properly).  You also
    cannot access the ``SOA``, see `SOA caveat`_.

.. _RRset types supported by PowerDNS: https://doc.powerdns.com/md/types/


Creating an RRset
~~~~~~~~~~~~~~~~~

To create a new RRset, simply issue a ``POST`` request to the
``/api/v1/domains/{domain}/rrsets/`` endpoint, like this::

    http POST \
        https://desec.io/api/v1/domains/{domain}/rrsets/ \
        Authorization:"Token {token}" \
        subname:='"www"' type:='"A"' records:='["127.0.0.1","127.0.0.2"]' ttl:=3600

``type``, ``records``, and ``ttl`` are mandatory, whereas the ``subname``
field is optional.

Upon success, the response status code will be ``201 Created``, with the RRset
contained in the response body.  If the ``records`` value was semantically
invalid or an invalid ``type`` was provided, ``422 Unprocessable Entity`` is
returned.  If the RRset could not be created for another reason (for example
because another RRset with the same name and type exists already, or because
not all required fields were provided), the API responds with ``400 Bad
Request``.


Retrieving all RRsets in a Zone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``/api/v1/domains/{domain}/rrsets/`` endpoint reponds to ``GET`` requests
with an array of `RRset object`_\ s. For example, you may issue the following
command::

    http GET \
        https://desec.io/api/v1/domains/{domain}/rrsets/ \
        Authorization:"Token {token}"

to retrieve the contents of a zone that you own.

The response status code is ``200 OK``.  This is true also if there are no
RRsets in the zone; in this case, the response body will be an empty JSON
array.


Filtering by Record Type
````````````````````````

To retrieve an array of all RRsets from your zone that have a specific type
(e.g. all ``A`` records, regardless of ``subname``), augment the previous
``GET`` request with a ``type`` query parameter carrying the desired RRset type
like::

    http GET \
        https://desec.io/api/v1/domains/{domain}/rrsets/?type={type} \
        Authorization:"Token {token}"


Filtering by Subname
````````````````````

To filter the RRsets array by subname (e.g. to retrieve all records in the
``www`` subdomain, regardless of their type), use the ``subname`` query
parameter, like this::

    http GET \
        https://desec.io/api/v1/domains/{domain}/rrsets/?subname={subname} \
        Authorization:"Token {token}"

This approach also allows to retrieve all records associated with the zone
apex (i.e. ``example.com`` where ``subname`` is empty), by querying
``rrsets/?subname=``.

Note the three dots after ``{subname}``.  You can think of them as
abbreviating the rest of the DNS name.  This approach also allows to retrieve
all records associated with the zone apex (i.e. ``example.com`` where
``subname`` is empty), by simply using the ``rrsets/.../``.


Retrieving a Specific RRset
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve an RRset with a specific name and type from your zone (e.g. the
``A`` record for the ``www`` subdomain), issue a ``GET`` request with the
``subname`` information and the type appended to the ``rrsets/`` endpoint,
like this::

    http GET \
        https://desec.io/api/v1/domains/{domain}/rrsets/{subname}.../{type}/ \
        Authorization:"Token {token}"

Note the three dots after ``{subname}``; you can think of them as abbreviating
the rest of the DNS name.  This will only return one RRset (i.e., the response
is not a JSON array).

The response status code is ``200 OK`` if the requested RRset exists, and
``404 Not Found`` otherwise.


Modifying an RRset
~~~~~~~~~~~~~~~~~~

To modify an RRset, use the endpoint that you would also use to retrieve that
specific RRset.  The API allows changing the values of ``records`` and
``ttl``.  When using the ``PATCH`` method, only fields you would like to modify
need to be provided, where the ``PUT`` method requires specification of both
fields.  Examples::

    http PUT \
        https://desec.io/api/v1/domains/{domain}/rrsets/{subname}.../{type}/ \
        Authorization:"Token {token}" records:='["127.0.0.1"]' ttl:=3600

    http PATCH \
        https://desec.io/api/v1/domains/{domain}/rrsets/{subname}.../{type}/ \
        Authorization:"Token {token}" ttl:=86400

If the RRset was updated successfully, the API returns ``200 OK`` with the
updated RRset in the reponse body.  If not all required fields were provided,
the API responds with ``400 Bad Request``.  If the ``records`` value was
semantically invalid, ``422 Unprocessable Entity`` is returned.  If the RRset
does not exist, ``404 Not Found`` is returned.


Deleting an RRset
~~~~~~~~~~~~~~~~~

To delete an RRset, you can send a ``DELETE`` request to the endpoint
representing the RRset. Alternatively, you can modify it and provide an empty
array for the ``records`` field (``[]``).

Upon success or if the RRset did not exist in the first place, the response
status code is ``204 No Content``.


General Notes
~~~~~~~~~~~~~

- All operations are performed on RRsets, not on the individual Resource
  Records.

- The TTL (time-to-live: time for which resolvers may cache DNS information)
  is a property of an RRset (and not of a record).  Thus, all records in an
  RRset share the record type and also the TTL.  (This is actually a
  requirement of the DNS specification and not an API design choice.)

- We have not done extensive testing for reverse DNS, but things should work in
  principle.  If you encounter any problems, please let us know.


Notes on Certain Record Types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generally, the API supports all `RRset types supported by PowerDNS`_, with a
few exceptions for such record types that the backend manages automatically.
Thus, these restrictions are not limitations from a practical point of view.
Furthermore, special care needs to be taken with some types of records, as
explained below.

.. _RRset types supported by PowerDNS: https://doc.powerdns.com/md/types/


Restricted Types
````````````````
**Note:**  Some record types are supported by the API, but not currently
served by our nameservers (such as ``ALIAS`` or ``DNAME``).  If you wish to
use such record types, shoot us an email.  In most cases, it should not be a
problem to enable such functionality.

``DNSKEY``, ``NSEC3PARAM``, ``RRSIG``
    These record types are meant to provide DNSSEC-related information in
    order to secure the data stored in your zones.  RRsets of this type are
    generated and served automatically by our nameservers.  However, you can
    neither read nor manipulate these RRsets through the API.  When attempting
    such operations, ``403 Forbidden`` is returned.

.. _`SOA caveat`:

``SOA`` record
    The ``SOA`` record cannot be read or written through this interface.  When
    attempting to create, modify or otherwise access an ``SOA`` record, ``403
    Forbidden`` is returned.

    The rationale behind this is that the content of the ``SOA`` record is
    entirely determined by the DNS operator, and users should not have to bother
    with this kind of metadata.  Upon zone changes, the backend automatically
    takes care of updating the ``SOA`` record accordingly.

    If you are interested in the value of the ``SOA`` record, you can retrieve
    it using a standard DNS query.


Caveats
```````

.. _`caveat on the priority field`:

Record types with priority field
    The deSEC DNS API does not explicitly support priority fields (as used for
    ``MX`` or ``SRV`` records and the like).

    Instead, the priority is expected to be specified at the beginning of the
    record content, separated from the rest of it by a space.

``CNAME`` record
    - The record value must be terminated by a dot ``.`` (as in
      ``example.com.``).

    - If you create a ``CNAME`` record, its presence will cause other RRsets of
      the same name to be hidden ("occluded") from the public (i.e. in
      responses to DNS queries).  This is per RFC 1912.

      However, as far as the API is concerned, you can still retrieve and
      manipulate those additional RRsets.  In other words, ``CNAME``-induced
      hiding of additional RRsets does not apply when looking at the zone
      through the API.

    - It is currently possible to create a ``CNAME`` RRset with several
      records.  However, this is not legal, and the response to queries for
      such RRsets is undefined.  In short, don't do it.

    - Similarly, you are discouraged from creating a ``CNAME`` RRset for the
      zone apex (main domain name, empty ``subname``).  Doing so will most
      likely break your domain (for example, any ``NS`` records that are
      present will disappear from DNS responses), and other undefined behavior
      may occur.  In short, don't do it.  If you are interested in aliasing
      the zone apex, consider using an ``ALIAS`` RRset.

``MX`` record
    The ``MX`` record value consists of the priority value and a mail server
    name, which must be terminated by a dot ``.``.  Example: ``10
    mail.a4a.de.``

``NS`` record
    The use of wildcard RRsets (with one component of ``subname`` being equal
    to ``*``) of type ``NS`` is **discouraged**.  This is because the behavior
    of wildcard ``NS`` records in conjunction with DNSSEC is undefined, per
    RFC 4592, Sec. 4.2.

``TXT`` record
    The contents of the ``TXT`` record must be enclosed in double quotes.
    Thus, when ``POST``\ ing to the API, make sure to do proper escaping etc.
    as required by the client you are using.  Here's an example of how to
    create a ``TXT`` RRset with HTTPie::

        http POST \
            https://desec.io/api/v1/domains/{domain}/rrsets/ \
            Authorization:"Token {token}" \
            type:='"TXT"' records:='["\"test value1\"","\"value2\""]' ttl:=3600
