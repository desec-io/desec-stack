.. _update-api:

IP Update API
~~~~~~~~~~~~~

In case you want to dig deeper, here are the details on how our IP update API
works.  We provide this API to be compatible with
most dynDNS clients. However, we also provide a RESTful API that is
more powerful and generally preferred over the legacy interface described here.

Please note that when using HTTPS (which we highly recommend), outdated setups
(such as TLS < 1.2) are not supported.  If you encounter SSL/TLS handshake
issues, you may have to update your dynDNS client and/or libraries used by it
(such as OpenSSL).

**Note:** Out of mercy for legacy clients (especially old routers), we still
accept unencrypted requests for this service.  We **urge** you to **use HTTPS
whenever possible**.

Update Request
``````````````
An IP update is performed by sending a ``GET`` request to ``update.dedyn.io``
via IPv4 or IPv6.
To enforce a specific IP version, you can either configure your client with
suitable flags (see examples below).
Alternatively, for IPv6, you can also use ``update6.dedyn.io``.

When the request is authenticated successfully, we use the connection IP
address and query parameters to update your domain's DNS ``A`` (IPv4) and
``AAAA`` (IPv6) records.  The new records will have a TTL value of 60 seconds
(that is, outdated values should disappear from DNS resolvers within that
time).

The request path can be chosen freely as long as it does not end in ``.ico``
or ``.png``.  HTTPS is recommended over HTTP.

.. _update-api-authentication:

IP Update Authentication
************************

You can authenticate your client in several ways. If authentication fails, the
API will return a ``401 Unauthorized`` status code.

Preferred method: HTTP Basic Authentication (with token)
--------------------------------------------------------
Encode your username and token secret (provided during registration) in the
``Authorization: Basic ...`` header. This is the method virtually all dynDNS
clients use out of the box.

**Important:** If your dynDNS client asks for a *password*, do not enter your
account password (if you have one). Instead, enter your token!


HTTP Token Authentication
------------------------------------------
Send an ``Authorization: Token  ...`` header along with your request, where
``...`` is the token secret issued at registration (or manually created later).

Query string method (discouraged)
---------------------------------
Set the ``username`` and ``password`` query string parameters (``GET
?username=...&password=...``).

**Important:** We **strongly discourage** using this method as it comes with a
subtle disadvantage: We log all HTTP request URLs for a few days to facilitate
debugging. As a consequence, this method will cause your token secret to end
up in our log files in clear text. The method is provided as an emergency
solution where folks need to deal with old and/or crappy clients. If this is
the case, we suggest looking for another client.


Determine Hostname
******************
To update your IP address in the DNS, our servers need to determine the
hostname you want to update.  To determine the hostname, we try the following
steps until there is a match:

- ``hostname`` query string parameter, unless it is set to ``YES`` (this
  sometimes happens with dynDNS update clients).

- ``host_id`` query string parameter.

- The username as provided in the HTTP Basic Authorization header.

- The username as provided in the ``username`` query string parameter.

- After successful authentication (no matter how), the only hostname that is
  associated with your user account (if not ambiguous).

If we cannot determine a hostname to update, the API returns a status code of
``400 Bad Request`` (if no hostname was given but multiple domains exist in
the account) or ``404 Not Found`` (if the specified domain was not found).

Subdomains
----------
The dynDNS update API can also be used to update IP records for subdomains.
To do so, make sure that in the above list of steps, the first value
provided contains the full domain name (including the subdomain).

Example: Your domain is ``yourdomain.dedyn.io``, and you're using HTTP Basic
Authentication.  In this case, replace your authentication username with
``sub.yourdomain.dedyn.io``.  Similarly, if you use the ``hostname`` query
parameter, it needs to be set to the full domain name (including subdomain).

To update more than one domain name, please see
:ref:`updating-multiple-dyn-domains`.

.. _determine-ip-addresses:

Determine IP Address(es)
************************
The last ingredient we need for a successful update of your DNS records is your
IPv4 and/or IPv6 addresses, for storage in the ``A`` and ``AAAA`` records,
respectively.

For IPv4, we check the query string parameters ``myip``, ``myipv4``, ``ip``
(in this order) for IPv4 addresses to record in the database.
Multiple IP addresses may be given as a comma-separated list.
When the special string ``preserve`` is provided instead, the configuration
on record (if any) will be kept as is.
If none of the parameters is set, the connection's client IP address will be
used if it is an IPv4 connection; otherwise the IPv4 address will be deleted
from the DNS.
IP deletion can also be forced by providing an empty value (e.g. ``myipv4=``).

For IPv6, the procedure is similar.
We check the ``myipv6``, ``ipv6``, ``myip``, ``ip`` query string parameters
(in this order) and the IP that was used to connect to the API for IPv6
addresses and use the first one found.
Both the multi-IP syntax and the ``preserve`` rule apply as above.
If nothing is found or an empty value provided, the ``AAAA`` record will be
deleted.

When using the ``myip`` parameter, a mixed-type list of both IPv4 and IPv6
addresses may be given.


Update Response
```````````````
If successful, the server will return a response with status ``200 OK`` and
``good`` as the body (as per the dyndns2 protocol specification). For error
status codes, see above.

dynDNS updates are subject to rate limiting.  For details, see
:ref:`rate-limits`.


Examples
````````
The examples below use ``<your domain>`` as the domain which is to be updated
(which could be a custom domain or a dedyn.io domain like
``yourdomain.dedyn.io``) and ``<your token secret>`` as an API token
affiliated with the respective account (see :ref:`manage-tokens` for details.)
``1.2.3.4`` is used as an example for an IPv4 address, ``fd08::1234`` as a
stand-in for an IPv6 address. Replace those (including the ``<`` and ``>``)
with your respective values.


Basic authentication with automatic IP detection (IPv4 **or** IPv6)::

  curl --user <your domain>:<your token secret> https://update.dedyn.io/

  curl https://update.dedyn.io/?hostname=<your domain> \
    --header "Authorization: Token <your token secret>"

Basic authentication with forced use of IPv4 (will remove IPv6 address from the DNS)::

  curl --ipv4 https://update.dedyn.io/?hostname=<your domain> \
    --header "Authorization: Token <your token secret>"

Basic authentication with forced use of IPv6 (will remove IPv4 address from the DNS)::

  curl --ipv6 https://update.dedyn.io/?hostname=<your domain> \
    --header "Authorization: Token <your token secret>"

  curl --user <your domain>:<your token secret> https://update6.dedyn.io/

Basic authentication with simultaneous update of IPv4 and IPv6::

  curl --user <your domain>:<your token secret> \
    "https://update.dedyn.io/?myipv4=1.2.3.4&myipv6=fd08::1234"

  curl "https://update6.dedyn.io/?hostname=<your domain>&myipv4=1.2.3.4&myipv6=fd08::1234" \
    --header "Authorization: Token <your token secret>"
