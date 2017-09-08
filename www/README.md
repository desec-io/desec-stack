deSEC www
=====

This docker container provides an nginx-implemented proxy server to all deSEC services. It is the frontend-access method.


Requirements
-----

Although most configuration is contained in this repository, some external dependencies need to be met before the created
docker image can be run. Dependencies are:

1. Various SSL certificates for the external hostnames. For the following hostnames, put certificate and private key files
   into a directory and mount it on /etc/ssl/private. Name the files ${NAME}.cer and ${NAME}.key respectively.
   - `MAIN` (e.g. desec.io)
   - `www`
   - `checkip.dedyn`
   - `checkipv4.dedyn`
   - `checkipv6.dedyn`
   - `update.dedyn`
   - `update6.dedyn`
   - `dedyn`
   - `www.dedyn`
2. DH Parameter file (create this with `openssl dhparam -out dhparam.pem 2048`)
   Put a suitable DH parameter file into the same mount location (see 1) and name it dhparam.pem.


How to Run
-----

Make sure you provide all the requirements (see above). 

Build the image (note the trailing dot):

    docker build -t www .

And then run the image (replace www1 by your favorite container name):

    docker run --name www1 -v /your/certificate/dir:/etc/ssl/private -P -d www


DNS Setup
------

The provided nginx will listen to the following names in your DOMAIN:

- `${DOMAIN}` (static content)
- `www.${DOMAIN}` (redirect to static content)
- `checkip.dedyn.${DOMAIN}` (return IP address)
- `checkipv4.dedyn.${DOMAIN}` (return IP address)
- `checkipv6.dedyn.${DOMAIN}` (return IP address)
- `update.dedyn.${DOMAIN}` (update IP address)
- `update6.dedyn.${DOMAIN}` (update IP address)

It may contact the following hostnames:

- `api` for API requests
