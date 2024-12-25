FROM alpine AS oqs-provider

RUN apk add --no-cache cmake git g++ make ninja openssl openssl-dev

ARG LIBOQS_VERSION="0.12.0"
ARG OQSPROVIDER_VERSION="0.8.0"

RUN if [ -z ${LIBOQS_VERSION} ]; then exit 1; fi;
RUN if [ -z ${OQSPROVIDER_VERSION} ]; then exit 2; fi;

RUN git clone --depth 1 --branch ${LIBOQS_VERSION} https://github.com/open-quantum-safe/liboqs.git
RUN git clone --depth 1 --branch ${OQSPROVIDER_VERSION} https://github.com/open-quantum-safe/oqs-provider.git

ARG liboqs_DIR=/.local
RUN cd liboqs && cmake -GNinja -DCMAKE_INSTALL_PREFIX=$liboqs_DIR -S . -B _build && cd _build && ninja && ninja install
RUN cd oqs-provider && cmake -S . -B _build && cmake --build _build && cmake --install _build

FROM node:lts AS webapp
RUN \
  apt-get update \
  && apt-get -y install gettext-base \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY webapp/package.json /usr/src/app/
RUN npm install

ARG DESECSTACK_API_SEPA_CREDITOR_ID
ARG DESECSTACK_API_SEPA_CREDITOR_NAME
ARG DESECSTACK_DOMAIN
ARG DESECSTACK_NS
ENV VITE_APP_DESECSTACK_NS=${DESECSTACK_NS} \
    VITE_APP_DESECSTACK_API_SEPA_CREDITOR_ID=${DESECSTACK_API_SEPA_CREDITOR_ID} \
    VITE_APP_DESECSTACK_API_SEPA_CREDITOR_NAME=${DESECSTACK_API_SEPA_CREDITOR_NAME} \
    VITE_APP_LOCAL_PUBLIC_SUFFIXES=dedyn.${DESECSTACK_DOMAIN} \
    VITE_APP_EMAIL=support@desec.${DESECSTACK_DOMAIN}

COPY webapp/ /usr/src/app/
RUN npm run build -- --emptyOutDir false


FROM nginx:mainline-alpine

# Add dependencies for our scripts
RUN apk add --no-cache bash openssl inotify-tools

# configure openssl to use OQS provider
COPY --from=oqs-provider /oqs-provider/_build/lib/oqsprovider.so /usr/local/lib/
RUN cat <<EOF  >> /etc/ssl/openssl.cnf
[provider_sect]
default = default_sect
oqsprovider = oqsprovider_sect
[default_sect]
activate = 1
[oqsprovider_sect]
activate = 1
module = /usr/local/lib/oqsprovider.so
EOF

# nginx configuration and entrypoint
COPY conf /etc/nginx
COPY entrypoint.sh .

# mountable ssl certificate and key directory
# (we don't want any keys in this repository)
VOLUME /etc/ssl/private

# mountable content for /.well-known/ ACME challenge
VOLUME /var/www/html

# mountable content for web app (remove default stuff in there)
RUN rm /usr/share/nginx/html/*
COPY html/503.html /usr/share/nginx/html
COPY --from=webapp /usr/src/app/dist /usr/share/nginx/html

CMD ["./entrypoint.sh"]
