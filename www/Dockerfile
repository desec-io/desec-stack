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
VOLUME /usr/share/nginx/html

CMD ["./entrypoint.sh"]
