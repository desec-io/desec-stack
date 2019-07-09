deSEC Stack
===========

This is a docker-compose application providing the basic stack for deSEC name services. It consists of

- `nslord`: Eventually authoritative DNS server (PowerDNS). DNSSEC keying material is generated here.
  - There is a cron hook installed to secure new zones with DNSSEC and to set NSEC3 parameters. For new zones under `dedyn.io`, `DS` records are set in the parent zone. Expected to be superseded by native DNSSEC support in the PowerDNS API.
- `nsmaster`: Stealth authoritative DNS server (PowerDNS). Receives fully signed AXFR zone transfers from `nslord`. No access to keys.
- `api`: RESTful API to create deSEC users and domains. Currently used for dynDNS purposes only.
- `dbapi`, `dblord`, `dbmaster`: MariaDB database services for `api`, `nslord`, and `nsmaster`, respectively. The `dbmaster` database is exposed at 3306 for TLS-secured replication.

Requirements
------------

Although most configuration is contained in this repository, some external dependencies need to be met before the application can be run. Dependencies are:

1.  We run this software with the `--userland-proxy=false` flag of the `dockerd` daemon, and recommend you do the same.

2.  Set up TLS-secured replication of the `nsmaster` database to feed your PowerDNS slaves.

    To generate the necessary keys and certificates, follow the instructions at https://dev.mysql.com/doc/refman/5.7/en/creating-ssl-files-using-openssl.html. In the `openssl req -newkey` steps, consider switching to a bigger key size, and add `-subj '/CN=slave.hostname.example'`. (It turned out that StartSSL and Let's Encrypt certificates do not work out of the box.)

3.  Set sensitive information and network topology using environment variables or an `.env` file. You need (you can use the `.env.default` file as a template):
    - global
      - `DESECSTACK_DOMAIN`: domain name under which the entire system will be running. The API will be reachable at https://desec.$DESECSTACK_DOMAIN/api/. For development setup, we recommend using `yourname.dedyn.io`
      - `DESECSTACK_NS`: the names of the authoritative name servers, i.e. names pointing to your slave name servers. Minimum 2.
    - network
      - `DESECSTACK_IPV4_REAR_PREFIX16`: IPv4 net, size /16, for assignment of internal container IPv4 addresses. **NOTE:** If you change this in an existing setup, you 
        need to manually update MySQL grant tables and the `nsmaster` supermaster table to update IP addresses! Better don't do it.
      - `DESECSTACK_IPV6_SUBNET`: IPv6 net, ideally /80 (see below)
      - `DESECSTACK_IPV6_ADDRESS`: IPv6 address of frontend container, ideally 0642:ac10:0080 in within the above subnet (see below)
    - certificates
      - `DESECSTACK_WWW_CERTS`: `./path/to/certificates` for `www` container. This directory is monitored for changes so that nginx can reload when new keys/certificates are provided. **Note:** The reload is done any time something changes in the directory. The relevant files are **not** watched individually.
      - `DESECSTACK_DBMASTER_CERTS`: `./path/to/certificates` for `dbmaster` container
    - API-related
      - `DESECSTACK_API_ADMIN`: white-space separated list of Django admin email addresses
      - `DESECSTACK_API_DEBUG`: Django debug setting. Must be True (default in `docker-compose.dev.yml`) or False (default otherwise)
      - `DESECSTACK_API_SEPA_CREDITOR_ID`: SEPA creditor ID for donations
      - `DESECSTACK_API_EMAIL_HOST`: when sending email, use this mail server
      - `DESECSTACK_API_EMAIL_HOST_USER`: username for sending email
      - `DESECSTACK_API_EMAIL_HOST_PASSWORD`: password for sending email
      - `DESECSTACK_API_EMAIL_PORT`: port for sending email
      - `DESECSTACK_API_SECRETKEY`: Django secret
      - `DESECSTACK_API_PSL_RESOLVER`: Resolver IP address to use for PSL lookups. If empty, the system's default resolver is used.
      - `DESECSTACK_DBAPI_PASSWORD_desec`: mysql password for desecapi
    - nslord-related
      - `DESECSTACK_DBLORD_PASSWORD_pdns`: mysql password for pdns on nslord
      - `DESECSTACK_NSLORD_APIKEY`: pdns API key on nslord
      - `DESECSTACK_NSLORD_CARBONSERVER`: pdns `carbon-server` setting on nslord (optional)
      - `DESECSTACK_NSLORD_CARBONOURNAME`: pdns `carbon-ourname` setting on nslord (optional)
      - `DESECSTACK_NSLORD_DEFAULT_TTL`: TTL to use by default, including for default NS records
    - nsmaster-related
      - `DESECSTACK_DBMASTER_PASSWORD_pdns`: mysql password for pdns on nsmaster
      - `DESECSTACK_DBMASTER_PASSWORD_replication_manager`: mysql password for `replication-master` user (sets up permissions for replication slaves)
      - `DESECSTACK_NSMASTER_APIKEY`: pdns API key on nsmaster (required so that we can execute zone deletions on nsmaster, which replicates to the slaves)
      - `DESECSTACK_NSMASTER_CARBONSERVER`: pdns `carbon-server` setting on nsmaster (optional)
      - `DESECSTACK_NSMASTER_CARBONOURNAME`: pdns `carbon-ourname` setting on nsmaster (optional)
    - replication-manager related
      - `DESECSTACK_REPLICATION_MANAGER_CERTS`: a directory where `replication-manager` (to configure slave replication) will dump the slave's TLS key and certificate

Running the standard stack will also fire up an instance of the `www` proxy service (see `desec-www` repository), assuming that the `desec-static` project is located under the `static` directory/symlink.

How to Run
----------

Development:

    $ ./dev

Production:

    $ docker-compose build && docker-compose up

Storage
-------
All important data is stored in the databases managed by the `db*` containers. They use Docker volumes which, by default, reside in `/var/lib/docker/volumes/desecstack_{dbapi,dblord,dbmaster}_mysql`.
This is the location you will want to back up. (Be sure to follow standard MySQL backup practices, i.e. make sure things are consistent.)

API Versions and Roadmap
------------------------

deSEC currently maintains the following API versions:

API Version | URL Prefix | Status                                   | Support Ends
----------- | ---------- | ---------------------------------------- | ------------
Version 1   | `/api/v1/` |  unstable, stable release exp. June 2019 | earliest 6 months after v2 is declared stable
Version 2   | `/api/v2/` |  unstable

You can find our documentation for all API versions at https://desec.readthedocs.io/. (Select the version of interest in the navigation bar.)

Notes on IPv6
-------------

This stack is IPv6-capable. Caveats:

  - It is not necessary to start the Docker daemon with `--ipv6` or `--fixed-cidr-v6`. However, it is recommended to run `dockerd` with `--userland-proxy=false` to avoid 
    exposing ports on the host IPv6 address through `docker-proxy`.

  - Topology: Assuming 2a01:4f8:a0:12eb::/64 is the host network, and we reserve 2a01:4f8:a0:12eb:deec::/80 for the deSEC stack. Docker has more or less established that 
    IPv6  addresses be composed of the /80 prefix and the container MAC address. We choose the private 06:42:ac MAC prefix, defining a /104 subnet. For the remaining 24 
    bits of the MAC and IPv6 address, the convention seems to be to use the last 24 bits from the internally assigned IPv4 address. However, the first 8 of these are 
    configurable through the `DESECSTACK_IPV4_REAR_PREFIX16` variable. Since we don't want public IPv6 addresses to change if the internal IPv4 net prefix changes, we use 
    `0x10` for bits at position 24--17. We thus arrive at the subnet 2a01:4f8:a0:12eb:deec:642:ac10:0/108 for our public IPv6-enabled Docker containers. The last 16 bits 
    of the IPv6 address we indeed take from the internally assigned IP address. The same procedure is used to set the MAC address of IPv6 containers (they begin with 
    `06:42:ac:10:`).

    All other traffic in the /80 subnet is unexpected and therefore rejected. This includes traffic for IPv6 addresses that Docker assigns. (If Docker uses the MAC address 
    for this purpose, the prefix is 02:42:ac which is not part of our public network, so we're safe.)

    Since the above topology is strictly determined by the /80 prefix and the MAC address, we hope that most of the hardcoding can be removed in the future.

  - Docker currently exposes IPv6-capable containers fully, without restriction. Therefore, it is necessary to set up a firewall, like (`ip6tables`)

        -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
        -A FORWARD -d 2a01:4f8:a0:12eb:deec:642:ac10:0/108 -i eth0 -j ACCEPT
        -A FORWARD -d 2a01:4f8:a0:12eb:deec::/80 -i eth0 -j REJECT --reject-with icmp6-port-unreachable

Development: Getting Started Guide
----------------------------------

As desec-stack utilizes a number of different technologies and software packages, it requires some effort to setup a stack ready for development.
While there are certainly many ways to get started hacking desec-stack, here is one way to do it.

1. **Requirements.** This guide is intended and tested on Ubuntu 18.04.
    However, many other Linux distributions will also do fine.
    For desec-stack, [docker](https://docs.docker.com/install/linux/docker-ce/ubuntu/) and [docker-compose](https://docs.docker.com/compose/install/) are required.
    Further tools that are required to start hacking are git and curl.
    Recommended, but not strictly required for desec-stack development is to use certbot along with Let's Encrypt and PyCharm.
    jq, httpie, libmysqlclient-dev, python3-dev (>= 3.7) and python3-venv (>= 3.7) are useful if you want to follow this guide.
    To install everything you need for this guide except docker and docker-compose, use

       sudo apt install curl git httpie jq libmysqlclient-dev python3.7-dev python3.7-venv

1. **Get the code.** Clone this repository to your favorite location.

       git clone git@github.com:desec-io/desec-stack.git

1. **Obtain Domain Names.** To run desec-stack, this guide uses a subdomain of dedyn.io provided by desec.io.
    Install the httpie software, `sudo apt install httpie` to run the following commands.
    1. Register a deSEC user account.

           http POST https://desec.io/api/v1/auth/users/ email:='"you@example.com"' password:='"secret"'
           http POST https://desec.io/api/v1/auth/token/login/ email:='"you@example.com"' password:='"secret"'

        The deSEC API will reply with an authentication token to the second request, similar to 

           {
               "auth_token": "i+T3b1h/OI+H9ab8tRS98stGtURe"
           }

        Setup a shell variable that holds the authentication token for future use:

           TOKEN=i+T3b1h/OI+H9ab8tRS98stGtURe

        Check your email and follow the instructions for completing the registration.

    2. Register a dedyn.io subdomain to run your desec-stack on it and set up the IP addresses.
        For this guide, we assume `example.dedyn.io`. Register it with:

           DOMAIN=example.dedyn.io
           http POST https://desec.io/api/v1/domains/ Authorization:"Token ${TOKEN}" name:='"'${DOMAIN}'"'

        If you receive an answer that is different from status code 201, chances are that the name you chose is already taken by someone else.
        In that case, repeat the last step with a new name.
        To setup the necessary IP address records, we create a couple of A and AAAA records that point to localhost.
        As preparation, create a JSON file `dns.json` with the following content defining the DNS setup for desec-stack:

           [
               {"type": "A",    "ttl":300, "records": ["127.0.0.1"], "subname": "desec"},
               {"type": "AAAA", "ttl":300, "records": ["::1"],       "subname": "desec"},
               {"type": "A",    "ttl":300, "records": ["127.0.0.1"], "subname": "*.desec"},
               {"type": "AAAA", "ttl":300, "records": ["::1"],       "subname": "*.desec"},

               {"type": "A",    "ttl":300, "records": ["127.0.0.1"], "subname": "dedyn"},
               {"type": "AAAA", "ttl":300, "records": ["::1"],       "subname": "dedyn"},
               {"type": "A",    "ttl":300, "records": ["127.0.0.1"], "subname": "*.dedyn"},
               {"type": "AAAA", "ttl":300, "records": ["::1"],       "subname": "*.dedyn"}
           ]

        We use the deSEC API to publish the DNS information as defined in `dns.json`:

           http POST https://desec.io/api/v1/domains/${DOMAIN}/rrsets/ Authorization:"Token ${TOKEN}" < dns.json

1. **Obtain certificates.** desec-stack requires SSL certificates for the above-mentioned `desec` and `dedyn` hostnames as well as for various subdomains.
    (For a complete list, see `www/README.md`.)
    While we recommend to obtain signed certificates from Let's Encrypt, it's also possible to let desec-stack generate self-signed certificates on startup
    by just skipping this step. To use the deSEC certbot hook, first download it to an appropriate location and set up your credentials and domain name.

       mkdir -p ~/bin
       cd ~/bin
       curl https://raw.githubusercontent.com/desec-utils/certbot-hook/master/hook.sh > desec_certbot_hook.sh
       touch .dedynauth; chmod 600 .dedynauth
       echo DEDYN_TOKEN=${TOKEN} >> .dedynauth
       echo DEDYN_NAME=${DOMAIN} >> .dedynauth
       chmod +x desec_certbot_hook.sh

    Now we use certbot to obtain certificates, using the DNS challenge for authentication.

       certbot \
           --config-dir certbot/config --logs-dir certbot/logs --work-dir certbot/work \
           --manual --text --preferred-challenges dns \
           --manual-auth-hook ~/bin/desec_certbot_hook.sh \
           --server https://acme-v02.api.letsencrypt.org/directory \
           -d "*.${DOMAIN}" certonly

    Note that the definition of config, logs and work dir are only necessary if you do not want to run certbot as root.
    Verifying the DNS challenge takes a while, so allow this command to take a couple of minutes.
    After successfully retrieving the certificate, you can find them in `certbot/config/live/$DOMAIN/`.
    To make them available to desec-stack (in the default location), we copy certificate and keys.
    In the project root directory,

       mkdir certs
       cd certs
       for SUBNAME in desec www.desec get.desec checkip.dedyn checkipv4.dedyn checkipv6.dedyn dedyn www.dedyn update.dedyn update6.dedyn
       do
           ln -s cer ${SUBNAME}.${DOMAIN}.cer
           ln -s key ${SUBNAME}.${DOMAIN}.key
       done

       cp ~/bin/certbot/config/live/${DOMAIN}/fullchain.pem cer
       cp ~/bin/certbot/config/live/${DOMAIN}/privkey.pem key

    The last two steps need to be repeated whenever the certificates are renewed.
    While any location for the certificates is fine, the `certs/` folder is configured to be ignored by git so that private keys do not accidentally end up being committed.

1. **Configure desec-stack.** As docker-compose application, desec-stack is configured by environment variables defined in the `.env` file in the project root directory.
    Because it contains sensitive information for each deployment, `.env` is not part of the repository and ignored by git.
    However, we ship `.env.default` and `.env.dev` with templates for production and development, respectively.
    `.env.dev` is almost good enough for a basic development system, so let's use that as a basis:

       sed "s/^DESECSTACK_DOMAIN=.*/DESECSTACK_DOMAIN=${DOMAIN}/" .env.dev > .env

    Optionally, edit the file and
    1. configure an email server host name, user name, and password to deliver emails can be included in `.env`. A convenient option is a MailTrap account.
    2. adjust the network prefixes in `.env` to avoid collisions with other local networks.

1. **Get desec-static.** Currently, a second clone is needed to start desec-stack. We are planning to remove this dependency.
    Static is responsible for the static content (i.e. website) of desec-stack.
    As it currently requires components which we may not distribute, the website in your deployment will be broken. This will not affect the API in any way.
    In the project root,

       rm static
       git clone https://github.com/desec-io/desec-static.git static
       mkdir static/ultima  # workaround for proprietary components

1. **Run desec-stack.** To run desec-stack, use

       ./dev

    If you run desec-stack for the first time, this will require a couple of downloads and take a while.
    Once it is up and running, you can query the API home endpoint:

       http GET https://desec.${DOMAIN}/api/v1/

    Congratulations, you have desec-stack up and running.
    Of course, as this setup is only on your local machine, DNS information will not be published into the public DNS.
    However, the desec-stack nameserver is available on localhost port 5321.
    To check if desec-stack is working as expected, you can query the desec-stack nameserver locally for any information that you saved using your API.

       EMAIL=john@example.com
       PASSWORD=insecure
       http POST https://desec.${DOMAIN}/api/v1/auth/users/ email:=\"${EMAIL}\" password:=\"${PASSWORD}\"
       TOKEN=$(http POST https://desec.${DOMAIN}/api/v1/auth/token/login/ email:=\"${EMAIL}\" password:=\"${PASSWORD}\" | jq -r .auth_token)
       http POST https://desec.${DOMAIN}/api/v1/domains/ Authorization:"Token ${TOKEN}" name:='"test.example"'
       http POST https://desec.${DOMAIN}/api/v1/domains/test.example/rrsets/ Authorization:"Token ${TOKEN}" type:=\"A\" ttl:=60 records:='["127.0.0.254"]'

    After registering a user with your API, creating a domain and publishing some info to the DNS, use

       dig @localhost -p 5321 test.example 

    to see if the nameserver is behaving as expected.

1. **(Optional) Configure PyCharm for API Development.** As a docker-compose application, desec-stack takes a while to start.
    Additionally, it is hard to connect a debugger to the docker containers.
    Our recommended solution is to develop the API using Django tests running outside the docker-compose application.
    This will dramatically decrease the time required for running the Django tests and enable just-in-time debugging in PyCharm.
    Also, it will enable you to browse dependencies code within PyCharm and thus ease debugging.

    1. To get started, we create a virtual python environment that (to some extend) mimics the python environment in the docker container.
        In the project root,

           cd api
           python3.7 -m venv venv
           source venv/bin/activate
           pip install wheel
           pip install -r requirements.txt

    1. At this point, Django is ready to run in the virtual environment created above.
        There are two things to consider when running Django outside the container.
        First, the environment variables as defined in the `.env` file need to be made available in the shell.
        This can be done with

           set -a && source ../.env && set +a

        Second, the API needs to be configured to use a local database instead of the dbapi host.
        (dbapi, of course, is unavailable outside the docker-compose application.)
        We have configured a test database in `settings_quick_test.py`. To use this configuration instead of the default `settings.py`, set the following environment variable:

           export DJANGO_SETTINGS_MODULE=api.settings_quick_test

        Finally, you can manage Django using the `manage.py` CLI.
        As an example, to run the tests, use

           python3 manage.py test

    1. Open the project root directory `desec-stack` in PyCharm and select File › Settings.
        1. In Project: desec-stack › Project Structure, mark the `api/` folder as a source folder.
        2. In Project: desec-stack › Project Interpreter, add a new interpreter. Choose "existing environment" and select `api/api/venv/bin/python3` from the project root.
        3. In Languages & Frameworks › Django, enable the Django support and set the Django project root to `api/`.

    1. From the PyCharm menu, select Run › Edit Configurations and select the "Django tests" template from the list.
        1. Open the Environment Variables dialog. Copy the contents of the `.env` file and paste it here.
        2. Fill the Custom Settings field with the path to the `settings_quick_test` module.

    1. To see if the test configuration is working, right click on the api folder in the project view and select Run Test.

    1. To use code inspection, click on Inspect Code… in PyCharm's Code menu and add a local custom scope with the following pattern:

           file:api//*.py&&!file:api/venv//*&&!file:api/manage.py&&!file:api/api/wsgi.py&&!file:api/desecapi/migrations//*

    From this point on, you are set up to use most of PyCharm's convenience features.

    1. For PyCharm's Python Console, the environment variables of your `.env` file and `DJANGO_SETTINGS_MODULE=api.settings_quick_test` need to be configured in Settings › Build, Execution, Deployment › Console › Django Console. (Note that if you need to work with the database, you need to initialize it first by running all migrations; otherwise, the model tables will be missing from the database.)
