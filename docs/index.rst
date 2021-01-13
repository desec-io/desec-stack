Welcome to the deSEC DNS API
============================

The deSEC DNS API is a REST interface that allows easy management of DNS
information.  The interface design aims for simplicity so that tasks such as
creating domains and manipulating DNS records can be handled with ease and in
an intuitive fashion.

Server-side operations, such as creation of domains or DNS records, generally
expect JSON-formatted user input in the body of the ``POST``, ``PATCH``, or
``PUT`` request (see below).  Unless otherwise documented, requests are
expected to come with a ``Content-Type: application/json`` header field and to
be sent via HTTPS using state-of-the-art encryption. (Outdated setups, e.g.
TLS < 1.2, are not supported.)

API functionality is demonstrated using the command line tool ``curl``.  To
pretty-print JSON output, process the data through ``jq``:  ``curl ... | jq .``.

**Windows users:** We are told that the ``curl`` commands in this documentation
sometimes do not work. In this case, try moving the request payload in front
of the ``curl`` call, like this::

    echo {"name": "example.com"} | curl -X POST https://desec.io/api/v1/domains/ --header "Authorization: Token {token}" --header "Content-Type: application/json" --data @-


.. toctree::
   :maxdepth: 2
   :caption: User Management

   quickstart
   auth/account
   auth/tokens


.. toctree::
   :maxdepth: 2
   :caption: DNS Management

   dns/domains
   dns/rrsets


.. toctree::
   :maxdepth: 2
   :caption: dynDNS

   dyndns/configure
   dyndns/lets-encrypt
   dyndns/update-api


.. toctree::
   :maxdepth: 2
   :caption: API Summary

   endpoint-reference
   rate-limits
   lifecycle


Getting Help
============

If you need help beyond this documentation, please do not hesitate and
shoot us an email at support@desec.io.

About this document
===================
To add to our documentation or fix a mistake, please submit a Pull Request
at https://github.com/desec-io/desec-stack.
