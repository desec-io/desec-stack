FROM ubuntu:jammy

COPY ./entrypoint.sh /root/
CMD ["/root/entrypoint.sh"]

RUN apt-get update && apt-get install -y \
    dnsutils \
    iptables \
    net-tools \
    dirmngr gnupg \
    # credentials management via envsubst
    && apt-get -y install gettext-base \
    --no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN set -ex \
    && echo 'deb [arch=amd64] http://repo.powerdns.com/ubuntu jammy-auth-48 main' \
        >> /etc/apt/sources.list \
    && echo 'Package: pdns-*' > /etc/apt/preferences.d/pdns \
    && echo 'Pin: origin repo.powerdns.com' >> /etc/apt/preferences.d/pdns \
    && echo 'Pin-Priority: 600' >> /etc/apt/preferences.d/pdns \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv 0x1B0C6205FD380FBB

RUN apt-get update \
    && apt-get install -y pdns-server pdns-backend-mysql faketime \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/powerdns/

COPY conf/ /etc/powerdns/
