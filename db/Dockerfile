FROM mariadb:10.1

# mountable ssl certificate and key directory
# (we don't want any keys in this repository)
VOLUME /etc/ssl/private/

COPY initdb.d/*.sql /docker-entrypoint-initdb.d/
COPY ./51-server.cnf /etc/mysql/conf.d/51-server.cnf
