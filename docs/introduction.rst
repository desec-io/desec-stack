Introduction
------------

The deSEC DNS API is a REST interface that allows easy management of DNS
information.  The interface design aims for simplicity so that tasks such as
creating domains and manipulating DNS records can be handled with ease and in
an intuitive fashion.

Server-side operations, such as creation of domains or DNS records, expect
JSON-formatted user input in the body of the ``POST``, ``PATCH``, or ``PUT``
request (see below).  The request is required to come with a ``Content-Type:
application/json`` header field.

For communication with the API, we recommend using `HTTPie`_ which takes care
of JSON encoding and the content type header automatically.  Of course,
``curl`` or any other decent HTTP client will work as well.

.. _HTTPie: https://httpie.org/


User Registration and Management
--------------------------------

User management is handled via Django's djoser library.  For usage, please
check the `djoser endpoint documentation`_.

.. _djoser endpoint documentation:
    https://djoser.readthedocs.io/en/latest/getting_started.html#available-endpoints

Most operations require authentication of the domain owner using a token that
is returned by djoser's ``token/create/`` endpoint.  To authenticate, this
token is transmitted via the HTTP ``Authorization`` header, as shown in the
examples in this document.
