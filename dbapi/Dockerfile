FROM postgres:16-alpine

RUN apk add --no-cache pwgen

USER postgres

# mountable storage
VOLUME /var/lib/postgresql/data

ENTRYPOINT ["entrypoint-wrapper.sh"]
CMD ["postgres"]

COPY entrypoint-wrapper.sh /usr/local/bin/
ADD docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
