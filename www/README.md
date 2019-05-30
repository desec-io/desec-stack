www
=====

This docker container provides an nginx-implemented proxy server to all deSEC services. It is the frontend-access method.


Certificate Setup
-----

Various SSL certificates for the external hostnames. For the following hostnames, put certificate and private key files into the certificate directory specified in your `.env` file. Name the files `${NAME}.cer` and `${NAME}.key` respectively, where `${NAME}` is one of:
   - `desec.${DESECSTACK_DOMAIN}` (e.g. desec.io)
   - `www.desec.${DESECSTACK_DOMAIN}`
   - `get.desec.${DESECSTACK_DOMAIN}`
   - `checkip.dedyn.${DESECSTACK_DOMAIN}`
   - `checkipv4.dedyn.${DESECSTACK_DOMAIN}`
   - `checkipv6.dedyn.${DESECSTACK_DOMAIN}`
   - `update.dedyn.${DESECSTACK_DOMAIN}`
   - `update6.dedyn.${DESECSTACK_DOMAIN}`
   - `dedyn.${DESECSTACK_DOMAIN}`
   - `www.dedyn.${DESECSTACK_DOMAIN}`

If `desec.${DESECSTACK_DOMAIN}.key` or `desec.${DESECSTACK_DOMAIN}.cer` cannot be found in your certificate folder, `www` will autogenerate self-signed certificate for all names on startup. This will provide a working, but untrusted service.
