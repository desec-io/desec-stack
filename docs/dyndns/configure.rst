Configuring your dynDNS Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's how to configure your client to send your IP address to our servers so
that we can publish it in the DNS. This works with both your own domains and
with dynDNS domains registered with us under dedyn.io. Depending on your use
case, one of the following options might be easier than the others.

To update your dynDNS IP address, there are several options:


Option 1: Use Your Router
`````````````````````````

For most folks, using the integrated dynDNS client of their router will be
easiest. Here are two ways how to configure it.

Use your router's deSEC provider
********************************

Some routers have support for deSEC out of the box, and you just need to select
the right option ("deSEC", "desec.io", "dedyn", or similar). For example, if
you run a router with the OpenWRT operation system, watch out for the
"desec.io" provider.

Custom Configuration
********************

If your router does not have deSEC preconfigured, the configuration procedure
will depend on the specific type of router which is why we can't provide a
tutorial for all of them. However, most of the time it boils down to enter the
following details in your router configuration:

- Update Server ``update.dedyn.io``, or Update URL ``https://update.dedyn.io/``
- Username (the full name of the domain you want to update, e.g. yourname.dedyn.io)
- Hostname (same as your username)
- Token secret (long random string for authentication, displayed after sign-up)

**Advanced API users:** The dynDNS token technically is a regular API token
with permissions restricted to DNS management (not allowing account
management).

**Note:** Please read the security warning at :ref:`determine-ip-addresses`.

IPv6 Support
------------
There is a chance that your router already properly supports pushing its IPv6
address to us. If it does not, you can try to let our servers determine your
IPv6 address by using IPv6 to connect. To see if this method works for you,
modify the "Update Server" or "Update URL" setting in your router's
configuration to ``update6.dedyn.io`` and ``https://update6.dedyn.io/``,
respectively.

Note that when using this update server, your IPv4 address will be deleted from
the DNS, and your domain will operate in IPv6-only mode. (For an explanation
why that is the case, see :ref:`determine-ip-addresses`.) It is **not** possible
to set up IPv4 and IPv6 by using both update servers in an alternating fashion.

To update both your IPv4 and IPv6 address at the same time, most routers need
to be configured with an update URL that provides both IP addresses via query string
parameters, e.g. ``https://update.dedyn.io/?myipv4=1.2.3.4&myipv6=fd08::1234``,
with the IP addresses replaced by placeholders. To find out the placeholder names
for your router, please refer to the manual of your device.

Example: Fritz!Box Devices
--------------------------

For Fritz!Box devices, for example, the corresponding URL reads:
``https://update.dedyn.io/?myipv4=<ipaddr>&myipv6=<ip6addr>``

=============================   =====
Field                           Entry
=============================   =====
DynDNS Provider                 User-defined
Update URL :superscript:`1`     ``https://update.dedyn.io/?myipv4=<ipaddr>&myipv6=<ip6addr>``
Domain Name                     <your domain>
Username :superscript:`2`       <your domain>
Password :superscript:`3`       <your authentication token secret>
=============================   =====

*Note 1*
  Note that the placeholders ``<ipaddr>`` and ``<ip6addr>`` in the update URL must
  remain unchanged; your router will substitute them automatically.  Furthermore,
  it is neither necessary nor recommended to use the placeholders ``<username>``
  and ``<passwd>`` in the URL, as the Fritz!Box also supports HTTP basic
  authentication which is more secure (see :ref:`update-api-authentication`).

*Note 2*
  **Not** your deSEC username! Instead, use the domain you want to update, for
  example ``yourdomain.dedyn.io``. See :ref:`update-api-authentication` for
  details.

*Note 3*
  A valid token secret for the domain. **Not** your deSEC account password!


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
the token secret that you received during registration. Last, tell ddclient how to
detect your IP address, your domain name and the update interval.
To test your setup, run ``sudo ddclient -force`` and see if everything works as
expected.

**Note:** As of the time of this writing, ddclient does not use an encrypted
HTTPS connection by default when the scheme "https://" is
missing from the URL. To enable it, open ``/etc/ddclient.conf`` and add
``ssl=yes`` above the ``server=`` statement or explicitly use "https://" in your URL.
We **strongly recommend** doing
so; otherwise, your credentials will be exposed during transmission.

Manual configuration (other systems)
************************************
After installing ddclient, you can start with a ``ddclient.conf`` configuration
file similar to this one, with the three placeholders replaced by your domain
name and your token secret::

  protocol=dyndns2
  # Run in daemon mode: auto-update DNS every 10min. (Alternatively, use cron.)
  #daemon=600
  # "use=cmd" and the curl command is one way of doing this; other ways exist
  use=cmd, cmd='curl https://checkipv4.dedyn.io/'
  ssl=yes
  server=update.dedyn.io
  login=[domain]
  password='[token secret]'
  [domain]

For more information, check out `these
<https://sourceforge.net/p/ddclient/wiki/routers/>`_ two `sections
<https://sourceforge.net/p/ddclient/wiki/usage/>`_ of the ddclient
documentation.

*Note 1*
  Exclusively on Debian and derivatives, since ddclient 3.8.2-3 you can enable
  IPv6 by replacing ``use`` with ``usev6``, ``checkipv4.dedyn.io`` with
  ``checkipv6.dedyn.io``, and ``update.dedyn.io`` with ``update6.dedyn.io``.
  There are some notes `here
  <https://github.com/ddclient/ddclient/blob/develop/docs/ipv6-design-doc.md>`_.

*Note 2*
  According to :ref:`determine-ip-addresses`, the IP used for connecting to
  the update server is also considered when trying to find an IPv6 address to
  assign to your domain.  So, if you connect via IPv6, this address will be
  set on your domain, *even if you did not provide it explicitly*.

  If you would like to *avoid* setting an IPv6 address automatically, and
  instead configure an address statically (or remove the address), you can add
  a the ``myipv6`` parameter on the domain section, like this:
  ``mydomain.dedyn.io&myipv6=`` (delete) or ``mydomain.dedyn.io&myipv6=::1``
  (static value)

To test your setup, run ``sudo ddclient -force`` and see if everything works as
expected.

**Note:** Please read the security warning at :ref:`determine-ip-addresses`.


.. _updating-multiple-dyn-domains:

Updating Multiple Domains
`````````````````````````
To update multiple domain or subdomains, it is best to designate one of them
as the main domain, and create CNAME records for the others, so that they act
as DNS aliases for the main domain.
You can use do that either via the web interface or the API.

If you try to update several subdomains directly (by issuing multiple update
requests), your update requests may be refused (see :ref:`rate-limits`).
