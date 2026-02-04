ARG DOCKER_REGISTRY
FROM ${DOCKER_REGISTRY}cznic/knot:v3.3.4

RUN set -ex \
    && apt-get update \
    && apt-get -y install gettext-base faketime python3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/knot /var/lib/knot
COPY conf/ /etc/knot/
COPY entrypoint.sh /usr/local/bin/
COPY zone_watch.py /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/zone_watch.py

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
