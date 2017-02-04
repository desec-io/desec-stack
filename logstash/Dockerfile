FROM logstash

COPY conf/syslog.conf /etc/logstash/
#RUN  cd /etc/logstash && curl -O "http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz" && gunzip GeoLite2-City.mmdb.gz

CMD ["-f", "/etc/logstash/syslog.conf"]

