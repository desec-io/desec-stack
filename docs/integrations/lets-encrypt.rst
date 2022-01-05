TLS Certificates with Let's Encrypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

certbot with deSEC Plugin
`````````````````````````
deSEC supports the ACME DNS challenge protocol to make it easy for you to
obtain wildcard certificates for your domain name easily from anywhere.
All you need is `certbot <https://certbot.eff.org/>`_, your credentials
and our `certbot plugin <https://pypi.org/project/certbot-dns-desec/>`_.


Other ACME Clients
``````````````````
Besides certbot, there are other ACME clients that support deSEC out of the box.
We currently know of the following:

- `acme.sh <https://github.com/Neilpang/acme.sh/wiki/dnsapi#71-use-desecio>`_
- `cert-manager web hook <https://github.com/kmorning/cert-manager-webhook-desec>`_
  (Kubernetes)
- `lego <https://github.com/go-acme/lego>`_
- `Posh-ACME <https://github.com/rmbolger/Posh-ACME/blob/main/Posh-ACME/Plugins/DeSEC-Readme.md>`_
- `Terraform vancluever/acme <https://registry.terraform.io/providers/vancluever/acme/latest/docs/guides/dns-providers-desec>`_

Our forum has a `more comprehensive list of tools and integrations around deSEC <https://talk.desec.io/t/tools-implementing-desec/11>`_.
