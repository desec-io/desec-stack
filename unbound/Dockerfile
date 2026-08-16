# Unbound is built from source because we need the flush_delegation command,
# which is not (yet) upstream. It removes the delegation of a name from the
# cache, including the parent-side NS RRset, the validator key cache entry, and
# the NSEC/NSEC3 records denying the DS -- without the latter, a newly created
# DS stays invisible until the denial expires.
# https://github.com/peterthomassen/unbound/tree/flush-delegation
# When flush_delegation lands upstream, drop the build stage and install the
# distribution package like everything else in this stack does.
ARG UNBOUND_COMMIT=407b674c070b98e7af7d0b4055443e73fbaad6b1

FROM debian:bookworm-slim AS build
ARG UNBOUND_COMMIT

RUN apt-get update && apt-get install -y --no-install-recommends \
    bison \
    ca-certificates \
    flex \
    gcc \
    git \
    libc6-dev \
    libevent-dev \
    libexpat1-dev \
    libssl-dev \
    make \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/peterthomassen/unbound.git /usr/local/src/unbound \
    && cd /usr/local/src/unbound \
    && git checkout ${UNBOUND_COMMIT} \
    && ./configure --prefix=/opt/unbound --with-libevent \
    && make -j$(nproc) \
    && make install


FROM debian:bookworm-slim

COPY ./entrypoint.sh /root/
CMD ["/root/entrypoint.sh"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libevent-2.1-7 \
    libexpat1 \
    openssl \
    # credentials management via envsubst
    gettext-base \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && adduser --system --group --no-create-home --home /opt/unbound unbound

COPY --from=build /opt/unbound/ /opt/unbound/
COPY conf/ /opt/unbound/etc/unbound/
RUN mkdir -p /opt/unbound/var && chown unbound:unbound /opt/unbound/var

ENV PATH=/opt/unbound/sbin:$PATH

EXPOSE 53/udp 53/tcp 8953/tcp
