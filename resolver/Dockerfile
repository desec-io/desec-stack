FROM ubuntu:noble

COPY ./entrypoint.sh /root/
CMD ["/root/entrypoint.sh"]

RUN apt-get update \
    && apt-get install -y bind9-dnsutils gettext-base unbound \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN cp /usr/share/dns/root.key /var/lib/unbound/root.key
COPY conf/ /etc/unbound/unbound.conf.d/
