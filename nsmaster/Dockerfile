FROM debian:jessie

RUN echo 'deb http://repo.powerdns.com/debian jessie-auth-40 main' \
      >> /etc/apt/sources.list \
 && echo 'Package: pdns-*' \
      > /etc/apt/preferences.d/pdns \
 && echo 'Pin: origin repo.powerdns.com' \
      >> /etc/apt/preferences.d/pdns \
 && echo 'Pin-Priority: 600' \
      >> /etc/apt/preferences.d/pdns

RUN set -ex \
	&& apt-key adv --keyserver hkp://pool.sks-keyservers.net --recv 0x1B0C6205FD380FBB \
	&& apt-get update \
	&& apt-get install -y pdns-server pdns-backend-mysql \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

VOLUME /etc/powerdns/

COPY ./entrypoint.sh /root/

CMD ["/root/entrypoint.sh"]
