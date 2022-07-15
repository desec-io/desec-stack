FROM postgres:13-alpine

RUN apk add --no-cache pwgen

ADD docker-entrypoint-initdb.d /docker-entrypoint-initdb.d

USER postgres

# mountable storage
VOLUME /var/lib/postgresql/data

COPY entrypoint-wrapper.sh /usr/local/bin/
ENTRYPOINT ["entrypoint-wrapper.sh"]
CMD ["postgres"]
