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
ENV VUE_APP_DESECSTACK_NS=${DESECSTACK_NS} \
    VUE_APP_DESECSTACK_API_SEPA_CREDITOR_ID=${DESECSTACK_API_SEPA_CREDITOR_ID} \
    VUE_APP_DESECSTACK_API_SEPA_CREDITOR_NAME=${DESECSTACK_API_SEPA_CREDITOR_NAME} \
    VUE_APP_LOCAL_PUBLIC_SUFFIXES=dedyn.${DESECSTACK_DOMAIN} \
    VUE_APP_EMAIL=support@desec.${DESECSTACK_DOMAIN}

COPY webapp/ /usr/src/app/
RUN npm run build -- --no-clean


FROM nginx:mainline-alpine

# Add dependencies for our scripts
RUN apk add --no-cache bash openssl inotify-tools

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
