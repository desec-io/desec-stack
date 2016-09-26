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

1. `./api-settings.py`: `api` configuration, in the style of `api/desecapi/settings_local.py.dist`

2. `./nslord/cronhook/insecure-zones.list`: list of zones that should not be DNSSEC-secured by the `nslord` cron hook. One zone per line, no trailing dot.

3. `./nslord/cronhook/my.cnf`: Configuration for the MariaDB/MySQL client, used by the `nslord` cron hook, to get the list of insecure zones from the `pdnslord` database.

4. Set up TLS-secured replication of the `pdnsmaster` database to feed your PowerDNS slaves.

   To generate the necessary keys and certificates, follow the instructions at https://dev.mysql.com/doc/refman/5.7/en/creating-ssl-files-using-openssl.html. In the `openssl req -newkey` steps, consider switching to a bigger key size, and add `-subj '/CN=slave.hostname.example'`. (It turned out that StartSSL and Let's Encrypt certificates do not work out of the box.)

Running the standard stack will also fire up an instance of the `www` proxy service (see `desec-www` repository), assuming that the `desec-static` project is located under the `static` directory/symlink. TLS certificates are assumed to be located in `certs`.


How to Run
-----

Development:

    ./dev

Production:

    docker-compose build && docker-compose up
