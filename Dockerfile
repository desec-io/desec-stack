FROM debian:jessie

COPY ./FD380FBB-pub.asc /root/
RUN echo 'deb http://repo.powerdns.com/debian jessie-auth-40 main' \
      >> /etc/apt/sources.list \
 && echo 'Package: pdns-*' \
      > /etc/apt/preferences.d/pdns \
 && echo 'Pin: origin repo.powerdns.com' \
      >> /etc/apt/preferences.d/pdns \
 && echo 'Pin-Priority: 600' \
      >> /etc/apt/preferences.d/pdns \\
 && cat /root/FD380FBB-pub.asc | apt-key add - 

RUN apt-get update && apt-get install -y \
    pdns-server \
    pdns-backend-mysql \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY ./pdns-mysql.conf /etc/powerdns/pdns.d/pdns.local.gmysql.conf
COPY ./pdns.conf /etc/powerdns/pdns.conf
COPY ./entrypoint.sh /root/

CMD ["/root/entrypoint.sh"]
