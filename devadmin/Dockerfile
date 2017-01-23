FROM richarvey/nginx-php-fpm:php5

RUN apk add --no-cache \
	php5-gettext \
	phpmyadmin

# Can't use /var/www/html/ because parent image defines it as a volume, but we're going to modify it at build time
ENV WEBROOT /var/www/htdocs

RUN mkdir /var/www/htdocs \
	&& cd /var/www/htdocs \
	&& wget https://github.com/poweradmin/poweradmin/archive/v2.1.7.tar.gz \
	&& tar xzf v2.1.7.tar.gz \
	&& rm -rf v2.1.7.tar.gz poweradmin-2.1.7/install/ \
	&& ln -s /usr/share/webapps/phpmyadmin phpmyadmin \
	&& ln -s poweradmin-2.1.7 poweradmin

COPY conf/phpmyadmin/config.inc.php /etc/phpmyadmin/
COPY conf/poweradmin/config.inc.php /var/www/htdocs/poweradmin-2.1.7/inc/

# Don't be smart
ENV TEMPLATE_NGINX_HTML=0
