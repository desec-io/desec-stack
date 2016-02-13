FROM richarvey/nginx-php-fpm

COPY ./poweradmin-2.1.7 /usr/share/nginx/html
COPY ./config.inc.php /usr/share/nginx/html/inc/config.inc.php

ENV TEMPLATE_NGINX_HTML=0
