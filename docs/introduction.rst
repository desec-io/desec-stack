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

