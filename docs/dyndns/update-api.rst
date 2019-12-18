IP Update API
~~~~~~~~~~~~~

In case you want to dig deeper, here are the details on how our IP update API
works.  We provide this API to be compatible with
most dynDNS clients. However, we also provide a RESTful API that is
more powerful and always preferred over the legacy interface described here.

Update Request
``````````````
An IP updates is performed by sending a GET request to ``update.dedyn.io`` via
HTTP or HTTPS. The path component can be chosen freely as long as it does not
end in ``.ico`` or ``.png``.

You can connect via IPv4 or IPv6. To enforce IPv6, use ``update6.dedyn.io``.

Please be aware that while we still accept unencrypted requests, we **urge**
you to use HTTPS. For that reason, we also send an HSTS header on HTTPS
connections.

Authentication
**************
You can authenticate your client in several ways:

- Preferred method: HTTP Basic Authentication. Encode your username and
  password as provided upon registration in the ``Authorization: Basic ...``
  header. This is the method virtually all dynDNS clients use out of the box.

- REST API method: HTTP Token Authentication. Send an ``Authorization: Token
  ...`` header along with your request, where ``...`` is an API token issued
  for this purpose. This method is used by our REST API as well.

- Set the ``username`` and ``password`` query string parameters (``GET
  ?username=...&password=...``). We **strongly discourage** using this
  method, but provide it as an emergency solution for situations where folks
  need to deal with old and/or crappy clients.

If we cannot authenticate you, the API will return a ``401 Unauthorized``
status code.

Determine Hostname
******************
To update your IP address in the DNS, our servers need to determine the
hostname you want to update (it's possible to set up several domains). To
determine the hostname, we try the following steps until there is a match:

- ``hostname`` query string parameter, unless it is set to ``YES`` (this
  sometimes happens with dynDNS update clients).

- ``host_id`` query string parameter.

- The username as provided in the HTTP Basic Authorization header.

- The username as provided in the ``username`` query string parameter.

- After successful authentication (no matter how), the only hostname that is
  associated with your user account (if not ambiguous).

If we cannot determine a hostname to update, the API will return a ``404 Not
Found`` status code. If the selected hostname is not eligible for dynamic
updates, we will return ``403 Forbidden``. This usually happens if you try
updating a hostname that is not under the ``dedyn.io`` domain. If you are
affected by this and would like to use another domain, please contact support.

.. _determine-ip-addresses:

Determine IP addresses
**********************
The last ingredient we need for a successful update of your DNS records is your
IPv4 and/or IPv6 addresses, for storage in the ``A`` and ``AAAA`` records,
respectively.

For IPv4, we will use the first IPv4 address it can find in the query string
parameters ``myip``, ``myipv4``, ``ip`` (in this order). If none of them is
set, it will use the IP that connected to the API, if a IPv4 connection was
made. If no address is found or if an empty value was provided instead of an IP
address, the ``A`` record will be deleted from the DNS.

For IPv6, the procedure is similar. We check ``myipv6``, ``ipv6``, ``myip``,
``ip`` query string parameters (in this order) and the IP that was used to
connect to the API for IPv6 addresses and use the first one found. If no
address is found or an empty value provided instead, the ``AAAA`` record will
be deleted.


Update Response
```````````````
If successful, the server will return a response with status ``200 OK`` and
``good`` as the body (as per the dyndns2 protocol specification). For error
status codes, see above.
