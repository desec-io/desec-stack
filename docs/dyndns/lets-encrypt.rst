TLS Certificate with Let's Encrypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

certbot with deSEC hook
```````````````````````

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

     wget https://raw.githubusercontent.com/desec-io/desec-certbot-hook/master/hook.sh
     wget https://raw.githubusercontent.com/desec-io/desec-certbot-hook/master/.dedynauth

#. **Get a token.** You need to configure an API token so that certbot can use
   it to authenticate its requests towards the deSEC API. The easiest way to
   get such a token is to log into the web interface at https://desec.io/,
   navigate to "Token Management", and create a token there.

#. **Configuration.** You need to provide your dedyn.io credentials to the hook
   script, so that it can write the Let's Encrypt challenge to the DNS on your
   behalf. To do so, edit the ``.dedynauth`` file to look something like::

    DEDYN_TOKEN=[your token]  # remove brackets, token from above step
    DEDYN_NAME=[yourdomain.example.com]  # remove brackets, add your domain to your desec.io account first

#. **Run certbot.** To obtain your certificate, run certbot in manual mode as
   follows. (For a detailed explanation, please refer to the certbot manual.)
   Please notice that you need to insert your domain name one more time. (Also,
   for users not familiar with shell commands, please note that you need to
   remove the ``\`` if you reformat the command to fit on one line.) ::

     certbot --manual --manual-auth-hook ./hook.sh --manual-cleanup-hook ./hook.sh \
         --preferred-challenges dns -d "YOURDOMAINNAME.dedyn.io" certonly
         
   You can also use certbot to get wildcard certificates like so::
   
     certbot --manual --manual-auth-hook ./hook.sh --manual-cleanup-hook ./hook.sh \
         --preferred-challenges dns -d "example.com" -d "*.example.com" certonly

   to make the process headless you can add ``--manual-public-ip-logging-ok -n``.

   Depending on how you installed certbot, you may need to replace ``certbot``
   with ``./certbot-auto`` (assuming that the ``certbot-auto`` executable is
   located in the current directory). Please also note that the hook script may
   wait up to two minutes to be sure that the challenge was correctly
   published.

   **Note:** To include subdomains in your certificate, you can specify the
   ``-d`` argument several times, e.g.
   ``-d "YOURDOMAINNAME.dedyn.io" -d "www.YOURDOMAINNAME.dedyn.io"``.

   If you would like to help improve this hook script, please check out our
   open issues at `<https://github.com/desec-io/desec-certbot-hook/issues>`_.
   We'd highly appreciate your help!


Other ACME clients
``````````````````
There are other ACME clients that support deSEC out of the box. We currently
know of the following:

- `acme.sh <https://github.com/Neilpang/acme.sh/wiki/dnsapi#71-use-desecio>`_
- `lego <https://github.com/go-acme/lego>`_
