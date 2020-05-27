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

.. _update-api-authentication:

IP Update Authentication
************************

You can authenticate your client in several ways. If authentication fails, the
API will return a ``401 Unauthorized`` status code.

Preferred method: HTTP Basic Authentication (with token)
--------------------------------------------------------
Encode your username and token (provided during registration) in the
``Authorization: Basic ...`` header. This is the method virtually all dynDNS
clients use out of the box.

**Important:** If you dynDNS client asks for a *password*, do not enter your
account password (if you have one). Instead, enter your token!


HTTP Token Authentication
------------------------------------------
Send an ``Authorization: Token  ...`` header along with your request, where
``...`` is the token issued at registration (or manually created later).

Query string method (discouraged)
---------------------------------
Set the ``username`` and ``password`` query string parameters (``GET
?username=...&password=...``).

**Important:** We **strongly discourage** using this method as it comes with a
subtle disadvantage: We log all HTTP request URLs for a few days to facilitate
debugging. As a consequence, this method will cause your secret token to end
up in our log files in clear text. The method is provided as an emergency
solution where folks need to deal with old and/or crappy clients. If this is
the case, we suggest looking for another client.


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

dynDNS updates are subject to rate limiting.  For details, see
:ref:`rate-limits`.


Examples
````````

The examples below use ``<your domain>.dedyn.io`` as the domain which is to be updated and
``<your authorization token>`` as an API token affiliated with the respective account.
(See :ref:`manage-tokens` for details.) ``<1.2.3.4>`` is used as an example for an IPv4 Address,
``<fd08::1234>`` as a standin for an IPv6 address. Replace those (including the ``<`` and ``>``)
with your respective values.


Basic authentication with automatic IP detection (IPv4 **or** IPv6)::

  curl --user <your domain>.dedyn.io:<your authorization token> https://update.dedyn.io
  
  curl https://update.dedyn.io/?hostname=<your domain>.dedyn.io \
    --header "Authorization: Token <your authorization token>"

Basic authentication with forced use of IPv6 (will remove IPv4 address from the DNS)::

  curl --user <your domain>.dedyn.io:<your authorization token> https://update6.dedyn.io
  
  curl https://update6.dedyn.io/?hostname=<your domain>.dedyn.io \
    --header "Authorization: Token <your authorization token>"

Basic authentication with simultaneous update of IPv4 and IPv6::

  curl --user <your domain>.dedyn.io:<your authorization token> \
    https://update.dedyn.io/?myipv4=1.2.3.4&myipv6=fd08::1234

  curl https://update6.dedyn.io/?hostname=<your domain>.dedyn.io?myipv4=<1.2.3.4>&myipv6=<fd08::1234> \
    --header "Authorization: Token <your authorization token>"

