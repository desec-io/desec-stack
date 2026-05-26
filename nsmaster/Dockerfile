FROM debian:bookworm-slim

# Install prerequisites for adding the vendor apt repo
RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-transport-https \
    curl \
    gnupg \
    ca-certificates \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Add CZ.NIC vendor repository for Knot DNS
RUN curl -fsSL https://pkg.labs.nic.cz/gpg \
        > /usr/share/keyrings/cznic-labs-pkg.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/cznic-labs-pkg.gpg] \
        https://pkg.labs.nic.cz/knot-dns bookworm main" \
        > /etc/apt/sources.list.d/cznic-labs-knot-dns.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    knot \
    knot-dnsutils \
    iproute2 \
    iptables \
    gettext-base \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Main config template (variables injected at startup via envsubst)
COPY conf/knot.conf.var /etc/knot/knot.conf.var

# Entrypoint and scripts
COPY entrypoint.sh    /root/entrypoint.sh
COPY export-zones.sh  /root/export-zones.sh
COPY import-zones.sh  /root/import-zones.sh
RUN chmod +x /root/entrypoint.sh /root/export-zones.sh /root/import-zones.sh

CMD ["/root/entrypoint.sh"]
