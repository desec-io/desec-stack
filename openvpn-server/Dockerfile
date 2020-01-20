FROM ubuntu:bionic

RUN apt-get update && apt-get install -y \
		iptables \
		openvpn \
		pimd \
	--no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY conf/ /etc/openvpn/
COPY entrypoint.sh .

VOLUME /etc/openvpn/secrets

CMD ["./entrypoint.sh"]
