Introduction
------------

The deSEC DNS API is a REST interface that allows easy management of DNS
information. The interface design aims for simplicity so that tasks such as
creating domains and manipulating DNS records can be handled with ease and in
an intuitive fashion.

We recommend using `HTTPie`_ for communication with the API, but ``curl`` or
any other decent HTTP client will work as well.

.. _HTTPie: https://httpie.org/


User Registration and Management
--------------------------------

User management is handled via Django's djoser library.  For usage, please
check the `djoser endpoint documentation`_.

.. _djoser endpoint documentation:
    https://djoser.readthedocs.io/en/latest/endpoints.html

Most operations require authentication of the domain owner using a token that
is returned by djoser's ``login/`` endpoint.  To authenticate, this token is
transmitted via the HTTP ``Authorization`` header, as shown in the examples in
this document.
