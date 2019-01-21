FROM mariadb:10.3

# Use random throw-away root password. Our init scripts switch authentication to socket logins only
ENV MYSQL_RANDOM_ROOT_PASSWORD=yes

# install tools used in init script
RUN set -ex && apt-get update && apt-get -y install gettext-base && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY initdb.d/* /docker-entrypoint-initdb.d/
RUN chown -R mysql:mysql /docker-entrypoint-initdb.d/

# mountable storage
VOLUME /var/lib/mysql
