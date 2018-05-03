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
contained in the response body.  If another RRset with the same name and type
exists already, the API responds with ``409 Conflict``.  If there is a
syntactical error (e.g. not all required fields were provided or the type was
not specified in uppercase), the API responds with ``400 Bad Request``.  If
field values were semantically invalid (e.g. when you provide an unknown record
type, or an `A` value that is not an IPv4 address), ``422 Unprocessable
Entity`` is returned.

Note that the values of ``type`` and ``subname`` as well as the ``records``
items are strings, and as such the JSON specification requires them to be
enclosed in double quotes (with the quotes being part of the field value);
your shell or programming language may require another layer of quotes!  By
contrast, ``ttl`` is an integer field, so the JSON value does not contain
quotes.

Creating a TLSA RRset
`````````````````````

A common use case is the creation of a ``TLSA`` RRset which carries information
about the TLS certificate used by the server that the domain points to.  For
example, to create a ``TLSA`` RRset for ``www.example.com``, you can run::

    http POST \
        https://desec.io/api/v1/domains/example.com/rrsets/ \
        Authorization:"Token {token}" \
        subname:='"_443._tcp.www"' type:='"TLSA"' ttl:=3600 \
        records:='["3 1 1 11501875615d4.....dd122bbf9190"]'

**Note:** The ``subname`` is prefixed with ``_{port}._{transport_protocol}``.
For a HTTPS server, this will usually be ``_443._tcp`` (for an otherwise empty
``subname``), or ``_443._tcp.www`` for the common ``www`` domain prefix.  For
other use cases, the values have to be adapted accordingly (e.g. ``_993._tcp``
for an IMAPS server).

To generate the ``TLSA`` from your certificate, you can use a tool like
https://www.huque.com/bin/gen_tlsa.  We are planning to provide a tool that is
connected directly to our API in the future.  For full detail on how ``TLSA``
records work, please refer to RFC 6698.

Bulk Creation of RRsets
```````````````````````

It is often desirable to create several RRsets at once.  This is achieved by
sending an array of RRset objects to the ``rrsets/`` endpoint (instead of just
one), like this::

    curl -X POST https://desec.io/api/v1/domains/{domain}/rrsets/ \
        -H "Content-Type: application/json" -H "Authorization: Token {token}" \
        -d '[{"subname": "www", "type": "A", "ttl": 3600, records: ["1.2.3.4"]},' \
            '{"subname": "www", "type": "AAAA", "ttl": 3600, records: ["c0::fefe"]},' \
            '...]'

This is especially useful for bootstrapping a new domain.

For details about input validation and return status codes, please refer to
`Bulk Operations`_.


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


Retrieving a Specific RRset
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve an RRset with a specific name and type from your zone (e.g. the
``A`` record for the ``www`` subdomain), issue a ``GET`` request with the
``subname`` information and the type appended to the ``rrsets/`` endpoint,
like this::

    http GET \
        https://desec.io/api/v1/domains/{domain}/rrsets/{subname}.../{type}/ \
        Authorization:"Token {token}"

This will return only one RRset (i.e., the response is not a JSON array).  The
response status code is ``200 OK`` if the requested RRset exists, and ``404
Not Found`` otherwise.

Note the three dots after ``{subname}``.  You can think of them as abbreviating
the rest of the DNS name.  To retrieve all records associated with the zone
apex (i.e. ``example.com`` where ``subname`` is empty), simply use
``rrsets/.../``.


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
updated RRset in the reponse body.  If there is a syntactical error (e.g. not
all required fields were provided or the type was not specified in uppercase),
the API responds with ``400 Bad Request``.  If field values were semantically
invalid (e.g. when you provide an unknown record type, or an `A` value that is
not an IPv4 address), ``422 Unprocessable Entity`` is returned.  If the RRset
does not exist, ``404 Not Found`` is returned.

Bulk Modification of RRsets
```````````````````````````

It is sometimes desirable to modify several RRsets at once.  This is achieved
by sending an array of RRset objects to the ``rrsets/`` endpoint (instead of
just one), like this::

    curl -X PUT https://desec.io/api/v1/domains/{domain}/rrsets/ \
        -H "Content-Type: application/json" -H "Authorization: Token {token}" \
        -d '[{"subname": "www", "type": "A", "ttl": 3600, records: ["1.2.3.4"]},' \
            '{"subname": "www", "type": "AAAA", "ttl": 3600, records: ["c0::fefe"]},' \
            '...]'

``subname`` and ``type`` must be specified for each given RRset.  For ``ttl``
and ``records``, the usual rules apply.

For details about input validation and return status codes, please refer to
`Bulk Operations`_.


Deleting an RRset
~~~~~~~~~~~~~~~~~

To delete an RRset, you can send a ``DELETE`` request to the endpoint
representing the RRset. Alternatively, you can modify it and provide an empty
array for the ``records`` field (``[]``).

Upon success or if the RRset did not exist in the first place, the response
status code is ``204 No Content``.

Bulk Deletion of RRsets
```````````````````````

It is sometimes desirable to delete RRsets as using a bulk request.  This is
achieved by sending the RRset with an empty records list ``[]`` to the
``rrsets/`` endpoint, using the ``PATCH`` or ``PUT`` method::

    curl -X PATCH https://desec.io/api/v1/domains/{domain}/rrsets/ \
        -H "Content-Type: application/json" -H "Authorization: Token {token}" \
        -d '[{"subname": "www", "type": "A", "ttl": 3600, records: ["1.2.3.4"]},' \
            '{"subname": "www", "type": "AAAA", records: []},' \
            '...]'

For details about input validation and return status codes, please refer to
`Bulk Operations`_.


Bulk Operations
~~~~~~~~~~~~~~~

The ``rrsets/`` endpoint supports bulk operations via the ``POST``, ``PATCH``,
and ``PUT`` request methods. You can simply send an array of RRset objects
(instead of just one), like this::

    curl -X PATCH https://desec.io/api/v1/domains/{domain}/rrsets/ \
        -H "Content-Type: application/json" -H "Authorization: Token {token}" \
        -d '[{"subname": "www", "type": "A",    "ttl": 3600, records: ["1.2.3.4"]},' \
            '{"subname": "www", "type": "AAAA", "ttl": 3600, records: ["c0::fefe", "c0ff::ee"]},' \
            '{"subname": "backup", "type": "MX", records: []},' \
            '...]'

Atomicity
`````````
Bulk operations are performed atomically, i.e. either all given RRsets are
accepted and published in (or deleted from) the DNS, or none of them are.

This allows you to smoothly apply large DNS changes to your domain *without*
running into the undesirable situation of an error showing up half-way through
the process when some changes already have been applied.

Field requirements
``````````````````
In all cases, the ``subname`` field is optional.  If missing, the empty subname
is assumed.

For the ``POST`` and ``PUT`` methods, all other fields are required for each
given RRset.  With ``POST``, only new RRsets are acceptable (i.e. the domain
must not yet have an RRset with the same subname and type), while ``PUT``
allows both creating new RRsets and modifying existing ones.

For the ``PATCH`` method, only ``type`` is required; if you want to modify only
``ttl`` or ``records``, you can skip the other field.  To create a new RRset
using ``PATCH``, all fields but ``subname`` must be specified.

To delete an RRset during a bulk operation, use ``PATCH`` or ``PUT`` and set
records to ``[]``.

Input validation
````````````````
For efficiency and other reasons, there are three stages of input validation:

1. Basic syntactical and semantical checks for missing JSON fields, negative
   TTL and such.

2. Uniqueness validation.  This is both to avoid the creation of multiple
   RRsets with the same subname and type, and to uncover bulk requests
   containing multiple parts that refer to the same subname and type.

3. Lastly, we check whether the given type is a supported DNS record type, and
   whether the given record contents are consistent with the type.

Errors are collected at each stage; if at least one error occured, the request
is aborted at the end of the stage, and the error(s) are returned.  Only if no
error occurred, will the request be allowed to proceed to the next stage.

In stages 1 and 2, errors are presented as a list of errors, with each list
item referring to one part of the bulk request, in the same order.  Parts that
did not cause errors have an empty error object ``{}``, and parts with errors
contain more details describing the error.  Unfortunately, in step 3, the API
currently does not associate the error message with the RRset that caused it.

The successive treatment of stages 1 and 2 means that one bulk part with a
stage-2 error may appear valid (``{}``) as long as another RRset has a stage-1
error.  Only after the stage-1 error is resolved, the request will reach stage
2, at which point an error may occur for the bulk part that previously seemed
valid.

Errors in stages 1 and 2 cause status code ``400`` (regardless of the exact
reason(s) which may vary across bulk parts), and errors from stage 3 cause
status code ``422``.


Notes
~~~~~

Consider the following general remarks that apply to our API as a whole:

- All operations are performed on RRsets, not on the individual Resource
  Records.

- The TTL (time-to-live: time for which resolvers may cache DNS information)
  is a property of an RRset (and not of a record).  Thus, all records in an
  RRset share the record type and also the TTL.  (This is actually a
  requirement of the DNS specification and not an API design choice.)

- We have not done extensive testing for reverse DNS, but things should work in
  principle.  If you encounter any problems, please let us know.


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
    such operations, ``403 Forbidden`` or ``400 Bad Request`` is returned,
    respectively.

.. _`SOA caveat`:

``SOA`` record
    The ``SOA`` record cannot be read or written through this interface.  When
    attempting to create, modify or otherwise access an ``SOA`` record, ``400
    Bad Request`` or ``403 Forbidden`` is returned, respectively.

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
    The deSEC DNS API does not explicitly support structured records fields
    (such as the priority field used for ``MX``, ``SRV`` and the like).

    Instead, those fields are expected to be concatenated in the conventional
    order used for zone files, with spaces in between them. For ``MX`` RRsets,
    that means that the priority is located at the beginning of the record
    content, separated from the rest of it by a space (e.g.
    ``10 mx.example.com.``).

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
