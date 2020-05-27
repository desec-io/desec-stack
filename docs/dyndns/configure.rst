Configuring your dynDNS Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's how to configure your client to send your IP address to our servers so
that we can publish it in the DNS. Depending on your use case, one of the
following options might be easier than the others.

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
- Token (long random string for authorization)

**Advanced API users:** The dynDNS token technically is a regular API token.
You can also use the token to make requests to our REST API. (Currently, all
tokens are equally powerful, i.e. a token used for dynDNS updates can also be
used to perform other kinds of API operations. Token scoping is on our
roadmap.)

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
parameters, e.g. ``https://update.dedyn.io/?myipv4=1.2.3.4&myipv6=fd08::1234``, and
provide placeholders for the respective addresses. To find out the placeholder names
for your router, please refer to the manual of your device.

Example: Fritz!Box Devices
--------------------------

For Fritz!Box devices, for example, the respective URL reads:
``https://update.dedyn.io/?myipv4=<ipaddr>&myipv6=<ip6addr>``.

=============================   =====
Field                           Entry
=============================   =====
DynDNS Provider                 User-defined
Update URL :superscript:`1`     ``https://update.dedyn.io/?myipv4=<ipaddr>&myipv6=<ip6addr>``
Domain Name :superscript:`2`    <your domain>.dedyn.io
Username :superscript:`3`       <your domain>.dedyn.io
Password :superscript:`4`       <your authorization token>
=============================   =====

*Note 1*
  Note that the placeholders ``<ipaddr>`` and ``<ip6addr>`` in the update URL must
  remain unchanged; your router will substitute them automatically. Furthermore,
  it is neither necessary nor recommended to use the placeholders ``<username>``
  and ``<passwd>`` as the Fritz!Box makes use of HTTP basic authentication,
  see :ref:`update-api-authentication`.

*Note 2*
  This entry is not used by deSEC - you only need to enter it as Fritz!Box mandates it

*Note 3*
  **Not** your deSEC username! Instead, use the domain you want to update,
  see :ref:`update-api-authentication` for details.

*Note 4*
  A valid access token for the domain. **Not** you deSEC account password!

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
the token that you received during registration. Last, tell ddclient how to
detect your IP address, your domain name and the update interval.

**Note:** As of the time of this writing, ddclient does not use an encrypted
HTTPS connection by default. To enable it, open ``/etc/ddclient.conf`` and add
``ssl=yes`` above the ``server=`` statement. We **strongly recommend** doing
so; otherwise, your credentials will be exposed during transmission.

Manual configuration (other systems)
************************************
After installing ddclient, you can start with a ``ddclient.conf`` configuration
file similar to this one, with the three placeholders replaced by your domain
name and your token::

  protocol=dyndns2
  # "use=cmd" and the curl command is one way of doing this; other ways exist
  use=cmd, cmd='curl https://checkipv4.dedyn.io/'
  ssl=yes
  server=update.dedyn.io
  login=[domain]
  password='[token]'
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
