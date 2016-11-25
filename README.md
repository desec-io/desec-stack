deSEC Stack
=====

This is a docker-compose application providing the basic stack for deSEC name services. It consists of

- `nslord`: Eventually authoritative DNS server (PowerDNS). DNSSEC keying material is generated here.
  - There is a cron hook installed to secure new zones with DNSSEC and to set NSEC3 parameters. For new zones under `dedyn.io`, `DS` records are set in the parent zone. Expected to be superseded by native DNSSEC support in the PowerDNS API.
- `nsmaster`: Stealth authoritative DNS server (PowerDNS). Receives fully signed AXFR zone transfers from `nslord`. No access to keys.
- `api`: RESTful API to create deSEC users and domains. Currently used for dynDNS purposes only.
- `db`: MariaDB database service for `nslord`, `nsmaster`, and `api`. Exposes `nsmaster` database (`pdnsmaster`) at 3306 for TLS-secured replication.
  - Note that, at the moment, storage is not a Docker volume, but local to the container. Thus, destroying the container destroys the database.
- `devadmin`: Web server with phpmyadmin and poweradmin for dev purposes.

**Note:** All passwords / keys are currently set to dummy values. You are supposed to replace them with sensible non-default values. We will make this easier in the future.


Requirements
-----

Although most configuration is contained in this repository, some external dependencies need to be met before the application can be run. Dependencies are:

1.  `./api-settings.py`: `api` configuration, in the style of `api/desecapi/settings_local.py.dist`

2.  `./nslord/cronhook/my.cnf`: Configuration for the MariaDB/MySQL client, used by the `nslord` cron hook, to get the list of insecure zones from the `pdnslord` database.

3.  Set up TLS-secured replication of the `pdnsmaster` database to feed your PowerDNS slaves.

    To generate the necessary keys and certificates, follow the instructions at https://dev.mysql.com/doc/refman/5.7/en/creating-ssl-files-using-openssl.html. In the `openssl req -newkey` steps, consider switching to a bigger key size, and add `-subj '/CN=slave.hostname.example'`. (It turned out that StartSSL and Let's Encrypt certificates do not work out of the box.)

4.  Set passwords etc. using environment variables or an `.env` file. You need:
    - `DESECSTACK_API_SECRETKEY`: Django secret
    - `DESECSTACK_DB_PASSWORD_root`: mysql root password
    - `DESECSTACK_DB_PASSWORD_desec`: mysql password for desecapi
    - `DESECSTACK_DB_PASSWORD_pdnslord`: mysql password for pdnslord
    - `DESECSTACK_DB_PASSWORD_pdnsmaster`: mysql password for pdnslord
    - `DESECSTACK_DB_PASSWORD_poweradmin`: poweradmin password
    - `DESECSTACK_DB_PASSWORD_ns1replication`: slave 1 replication password
    - `DESECSTACK_DB_SUBJECT_ns1replication`: slave 1 replication SSL certificate subject name
    - `DESECSTACK_DB_PASSWORD_ns2replication`: slave 2 replication password
    - `DESECSTACK_DB_SUBJECT_ns2replication`: slave 2 replication SSL certificate subject name
    - `DESECSTACK_DEVADMIN_PASSWORDmd5`: poweradmin password MD5 hash (if you're planning to use the dev environment)
    - `DESECSTACK_NSLORD_APIKEY`: pdns API key

Running the standard stack will also fire up an instance of the `www` proxy service (see `desec-www` repository), assuming that the `desec-static` project is located under the `static` directory/symlink. TLS certificates are assumed to be located in `certs`.


How to Run
-----

Development:

    $ ./dev

Production:

    $ docker-compose build && docker-compose up


Storage
---
All important data is stored in the database managed by the `db` container. It uses a Docker volume which, by default, resides in `/var/lib/docker/volumes/desecstack_mysql`.
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
