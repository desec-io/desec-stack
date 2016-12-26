deSEC Stack
=====

This is a docker-compose application providing the basic stack for deSEC name services. It consists of

- `nslord`: Eventually authoritative DNS server (PowerDNS). DNSSEC keying material is generated here.
  - There is a cron hook installed to secure new zones with DNSSEC and to set NSEC3 parameters. For new zones under `dedyn.io`, `DS` records are set in the parent zone. Expected to be superseded by native DNSSEC support in the PowerDNS API.
- `nsmaster`: Stealth authoritative DNS server (PowerDNS). Receives fully signed AXFR zone transfers from `nslord`. No access to keys.
- `api`: RESTful API to create deSEC users and domains. Currently used for dynDNS purposes only.
- `dbapi`, `dblord`, `dbmaster`: MariaDB database services for `api`, `nslord`, and `nsmaster`, respectively. The `dbmaster` database is exposed at 3306 for TLS-secured replication.
- `devadmin`: Web server with phpmyadmin and poweradmin for dev purposes.


Requirements
-----

Although most configuration is contained in this repository, some external dependencies need to be met before the application can be run. Dependencies are:

1.  We run this software with the `--userland-proxy=false` flag of the `dockerd` daemon, and recommend you do the same.

2.  Set up TLS-secured replication of the `nsmaster` database to feed your PowerDNS slaves.

    To generate the necessary keys and certificates, follow the instructions at https://dev.mysql.com/doc/refman/5.7/en/creating-ssl-files-using-openssl.html. In the `openssl req -newkey` steps, consider switching to a bigger key size, and add `-subj '/CN=slave.hostname.example'`. (It turned out that StartSSL and Let's Encrypt certificates do not work out of the box.)

3.  Set sensitive information and network topology using environment variables or an `.env` file. You need (you can use the `.env.default` file as a template):
    - network
      - `DESECSTACK_IPV6_SUBNET`: IPv6 net, ideally /80 (see below)
      - `DESECSTACK_IPV6_ADDRESS`: IPv6 address of frontend container, ideally 0642:ac10:0080 in within the above subnet (see below)
    - certificates
      - `DESECSTACK_WWW_CERTS`: `./path/to/certificates` for `www` container
      - `DESECSTACK_DBMASTER_CERTS`: `./path/to/certificates` for `dbmaster` container
    - API-related
      - `DESECSTACK_API_ADMIN`: white-space separated list of Django admin email addresses
      - `DESECSTACK_API_ALLOWED_HOSTS`: white-space separated list of hostnames for which the API listens
      - `DESECSTACK_API_DEBUG`: Django debug setting. Must be True (default in `docker-compose.dev.yml`) or False (default otherwise)
      - `DESECSTACK_API_SEPA_CREDITOR_ID`: SEPA creditor ID for donations
      - `DESECSTACK_API_EMAIL_HOST`: when sending email, use this mail server
      - `DESECSTACK_API_EMAIL_HOST_USER`: username for sending email
      - `DESECSTACK_API_EMAIL_HOST_PASSWORD`: password for sending email
      - `DESECSTACK_API_EMAIL_PORT`: port for sending email
      - `DESECSTACK_API_SECRETKEY`: Django secret
      - `DESECSTACK_DBAPI_PASSWORD_desec`: mysql password for desecapi
    - nslord-related
      - `DESECSTACK_DBLORD_PASSWORD_pdns`: mysql password for pdns on nslord
      - `DESECSTACK_DBLORD_PASSWORD_poweradmin`: mysql password for poweradmin (can write to nslord database! use for development only.)
      - `DESECSTACK_NSLORD_APIKEY`: pdns API key on nslord
      - `DESECSTACK_NSLORD_CARBONSERVER`: pdns `carbon-server` setting on nslord (optional)
      - `DESECSTACK_NSLORD_CARBONOURNAME`: pdns `carbon-ourname` setting on nslord (optional)
    - nsmaster-related
      - `DESECSTACK_DBMASTER_PASSWORD_pdns`: mysql password for pdns on nsmaster
      - `DESECSTACK_DBMASTER_PASSWORD_ns1replication`: slave 1 replication password
      - `DESECSTACK_DBMASTER_SUBJECT_ns1replication`: slave 1 replication SSL certificate subject name
      - `DESECSTACK_DBMASTER_PASSWORD_ns2replication`: slave 2 replication password
      - `DESECSTACK_DBMASTER_SUBJECT_ns2replication`: slave 1 replication SSL certificate subject name
      - `DESECSTACK_NSMASTER_CARBONSERVER`: pdns `carbon-server` setting on nsmaster (optional)
      - `DESECSTACK_NSMASTER_CARBONOURNAME`: pdns `carbon-ourname` setting on nsmaster (optional)
    - devadmin-related
      - `DESECSTACK_DEVADMIN_PASSWORD_poweradmin`: poweradmin password (if you're planning to use the dev environment)
      - `DESECSTACK_DEVADMIN_SESSIONKEY_poweradmin`: poweradmin session key

Running the standard stack will also fire up an instance of the `www` proxy service (see `desec-www` repository), assuming that the `desec-static` project is located under the `static` directory/symlink.


How to Run
-----

Development:

    $ ./dev

Production:

    $ docker-compose build && docker-compose up


Storage
---
All important data is stored in the databases managed by the `db*` containers. They use Docker volumes which, by default, reside in `/var/lib/docker/volumes/desecstack_{dbapi,dblord,dbmaster}_mysql`.
This is the location you will want to back up. (Be sure to follow standard MySQL backup practices, i.e. make sure things are consistent.)


Notes on IPv6
-----

This stack is IPv6-capable. Caveats:

  - It is not necessary to start the Docker daemon with `--ipv6` or `--fixed-cidr-v6`. However, it is recommended to run `dockerd` with `--userland-proxy=false` to avoid 
    exposing ports on the host IPv6 address through `docker-proxy`.

  - Due to various issues with Docker and docker-compose, IP addresses are current hardcoded (see [`docker-compose.yml`](docker-compose.yml) and the `TODO` flags therein).

  - Docker currently exposes IPv6-capable containers fully, without restriction. Therefore, it is necessary to set up a firewall, like (`ip6tables`)

        -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
        -A FORWARD -d 2a01:4f8:a0:12eb:deec:642:ac10:0/108 -i eth0 -j ACCEPT
        -A FORWARD -d 2a01:4f8:a0:12eb:deec::/80 -i eth0 -j REJECT --reject-with icmp6-port-unreachable

    Topology: 2a01:4f8:a0:12eb::/64 is the host network, and we reserve 2a01:4f8:a0:12eb:deec::/80 for the deSEC stack. Docker has more or less established that IPv6 
    addresses be composed of the /80 prefix and the container MAC address. We choose the private 06:42:ac MAC prefix, defining a /104 subnet. For the remaining 24 bits of 
    the MAC and IPv6 address, we again follow the convention and use the 24 last bits from the assigned IPv4 address, the first 4 of which are constant (since IPv4 
    addresses reside in 172.16.0.0/12). We thus arrive at the subnet 2a01:4f8:a0:12eb:deec:642:ac10:0/108 for our public IPv6-enabled Docker containers.

    All other traffic in the /80 subnet is unexpected and therefore rejected. This includes traffic for IPv6 addresses that Docker assigns. (If Docker uses the MAC address 
    for this purpose, the prefix is 02:42:ac which is not part of our public network, so we're safe.)

    Since the above topology is strictly determined by the /80 prefix and the MAC address, we hope that most of the hardcoding can be removed in the future.
