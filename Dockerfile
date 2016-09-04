FROM richarvey/nginx-php-fpm

RUN apk add --no-cache php5-gettext

COPY ./poweradmin-2.1.7 /var/www/html
COPY ./config.inc.php /var/www/html/inc/config.inc.php

ENV TEMPLATE_NGINX_HTML=0
