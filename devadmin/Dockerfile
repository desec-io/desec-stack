FROM richarvey/nginx-php-fpm

RUN apk add --no-cache \
	php5-gettext \
	phpmyadmin

RUN chmod -v 644 /etc/phpmyadmin/config.inc.php
RUN sed -i 's/localhost/db/g' /etc/phpmyadmin/config.inc.php

ENV TEMPLATE_NGINX_HTML=0
