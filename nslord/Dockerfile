FROM ubuntu:bionic

RUN apt-get update && apt-get install -y \
		dnsutils \
		net-tools \
		dirmngr gnupg \
	--no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN set -ex \
	&& apt-key adv --keyserver keyserver.ubuntu.com --recv 0x1B0C6205FD380FBB \
	&& apt-get update \
	# credentials management via envsubst
	&& apt-get -y install gettext-base \
	# pdns build dependencies
	&& apt-get -y install \
	    libcurl4-openssl-dev luajit lua-yaml-dev libyaml-cpp-dev libtolua-dev lua5.3 autoconf automake ragel bison \
	    flex g++ libboost-all-dev libtool make pkg-config libssl-dev virtualenv lua-yaml-dev libyaml-cpp-dev \
	    libluajit-5.1-dev libcurl4 gawk git libmysql++-dev \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt
ADD pdns /opt/pdns/
RUN cd /opt/pdns/ \
    && ls -lh \
    && autoreconf -vi \
    && ./configure --with-modules=gmysql --without-lua --disable-lua-records \
    && make \
    && make install

RUN rm -rf /etc/powerdns/
COPY conf/ /etc/powerdns/

COPY ./entrypoint.sh /root/

CMD ["/root/entrypoint.sh"]
