dynDNS Howto
------------

The following subsections contain information on the most common topics of
interest in the context of our DNSSEC-secured dynDNS service at dedyn.io.


Configuring your dynDNS Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's how to configure your client to send your IP address to our servers so
that we can publish it in the DNS. Depending on your use case, one of the
following options might be easier than the others.

To update your dynDNS IP address, there are three options:

Option 1: Use Your Router
`````````````````````````
For most folks, using the integrated dynDNS client of their router will be
easiest. The configuration procedures vary for all routers which is why we
can't provide a tutorial for all of them. However, most of the time it boils
down to enter the following details in your router configuration:

- Update Server ``update.dedyn.io``, or Update URL ``https://update.dedyn.io/``
- Username (your dedyn.io hostname, e.g. yourname.dedyn.io)
- Hostname (same as your username)
- Password (as provided when you registered your domain with us)

**Advanced API users only:** The dynDNS password technically is an API token.
If you also use our REST API, make sure to use a token for this purpose. Do not
enter your account password when setting up your domain!

IPv6 Support
************
There is a chance that your router already properly supports pushing its IPv6
address to us. If it does not, you can try to let our servers determine your
IPv6 address by using IPv6 to connect. To see if this method works for you,
modify the "Update Server" or "Update URL" setting in your router's
configuration to ``update6.dedyn.io`` and ``https://update6.dedyn.io/``,
respectively.

Note that when using this update server, your IPv4 address will be deleted from
the DNS, and your domain will operate in IPv6-only mode. (For an explanation
why that is the case, see `Determine IP addresses`_.) It is **not** possible to
set up IPv4 and IPv6 by using both update servers in an alternating fashion.

To update both your IPv4 and IPv6 address at the same time, most routers need
to be configured with an update URL that provides both IP addresses. For
Fritz!Box devices, for example, the URL reads:
``https://update.dedyn.io/?myipv4=<ipaddr>&myipv6=<ip6addr>`` (Note that the
placeholders in this URL must remain unchanged; your router will substitute
them automatically. To find out the placeholder names for your router, please
refer to the manual of your device.)

Option 2: Use ddclient
``````````````````````

Automatic configuration (Debian-/Ubuntu-based systems)
******************************************************
If you're on Debian, Ubuntu or any other Linux distribution that provides you
with the ddclient package, you can use it to update your IP address with our
servers. Note that depending on the ddclient version you are using, IPv6
support may be limited.

To install ddclient, run ``sudo apt-get install ddclient``. If a configuration
dialog does not appear automatically, use ``sudo dpkg-reconfigure ddclient`` to
start the configuration process.

In the configuration process, select "other" dynamic DNS service provider, and
enter ``update.dedyn.io`` as the dynamic DNS server. Next, tell ddclient to use
the "dyndns2" protocol to perform updates. Afterwards, enter the username and
password that you received during registration. Last, tell ddclient how to
detect your IP address, your domain name and the update interval.

**Note:** As of the time of this writing, ddclient does not use an encrypted
HTTPS connection by default. To enable it, open ``/etc/ddclient.conf`` and add
``ssl=yes`` above the ``server=`` statement. We **strongly recommend** doing
so; otherwise, your credentials will be exposed during transmission.

Manual configuration (other systems)
************************************
After installing ddclient, you can start with a ``ddclient.conf`` configuration
file similar to this one, with the three placeholders replaced by your domain
name and password::

  protocol=dyndns2
  # "use=cmd" and the curl command is one way of doing this; other ways exist
  use=cmd, cmd='curl https://checkipv4.dedyn.io/'
  ssl=yes
  server=update.dedyn.io
  login=[domain]
  password='[password]'
  [domain]

For more information, check out `these
<https://sourceforge.net/p/ddclient/wiki/routers/>`_ two `sections
<https://sourceforge.net/p/ddclient/wiki/usage/>`_ of the ddclient
documentation.

**Hint:** We have been told that in newer versions of ddclient, IPv6 can be
enabled by replacing ``use`` with ``usev6``, ``checkipv4.dedyn.io`` with
``checkipv6.dedyn.io``, and ``update.dedyn.io`` with ``update6.dedyn.io``.
Unfortunately, there seems to be no documentation of the ``usev6`` setting, so
we don't know if it is reliable. If you know more about this, please open an
issue or pull request at `<https://github.com/desec-io/desec-stack/>`_.

To test your setup, run ``sudo ddclient -force`` and see if everything works as
expected.


TLS Certificate with Let's Encrypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
dynDNS by deSEC supports the DNS challenge protocol to make it easy for you to
obtain certificates for your domain name easily from anywhere. All you need is
`certbot <https://certbot.eff.org/>`_, your credentials and our certbot hook
script. As always, we appreciate your feedback. Shoot us an email!

To obtain a Let's Encrypt Certificate for your dedyn.io domain, follow these
steps.

#. **Install Certbot.** There are many ways to install certbot, depending on
   your distribution and preference. Please follow the official instructions at
   `<https://certbot.eff.org/>`_.

#. **Install hook script.** To authenticate your dedyn.io domain against Let's
   Encrypt using the DNS challenge mechanism, you will need to update your
   domain according to instructions provided by Let's Encrypt. Our hook script
   automatizes this process for you. To use it, download the following two
   files and place them into a directory of your choice. Make sure to change
   the owner/permissions of the file (``chown``/``chmod``), so that it is only
   readable by your certbot user (usually ``root``). ::

     wget https://raw.githubusercontent.com/desec-io/certbot-hook/master/hook.sh
     wget https://raw.githubusercontent.com/desec-io/certbot-hook/master/.dedynauth

#. **Configuration.** You need to provide your dedyn.io credentials to the hook
   script, so that it can write the Let's Encrypt challenge to the DNS on your
   behalf. To do so, edit the ``.dedynauth`` file to look something like::

    DEDYN_TOKEN=your token / dynDNS password
    DEDYN_NAME=yourdomain.dedyn.io

#. **Run certbot.** To obtain your certificate, run certbot in manual mode as
   follows. (For a detailed explanation, please refer to the certbot manual.)
   Please notice that you need to insert your domain name one more time. (Also,
   for users not familiar with shell commands, please note that you need to
   remove the ``\`` if you reformat the command to fit on one line.) ::

     certbot --manual --preferred-challenges dns --manual-auth-hook ./hook.sh \
             -d "YOURDOMAINNAME.dedyn.io" certonly

   Depending on how you installed certbot, you may need to replace ``certbot``
   with ``./certbot-auto`` (assuming that the ``certbot-auto`` executable is
   located in the current directory). Please also note that the hook script may
   wait up to two minutes to be sure that the challenge was correctly
   published.

   **Note:** To include subdomains in your certificate, you can specify the
   ``-d`` argument several times, e.g.
   ``-d "YOURDOMAINNAME.dedyn.io" -d "www.YOURDOMAINNAME.dedyn.io"``.

   If you would like to help improve this hook script, please check out our
   open issues at `<https://github.com/desec-utils/certbot-hook/issues>`_. We'd
   highly appreciate your help!


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
Found`` status code.

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
