FROM nginx:1.11-alpine

# Add bash for our entrypoint script
RUN apk add --no-cache bash

# nginx configuration and entrypoint
COPY conf /etc/nginx
COPY entrypoint.sh .

# mountable ssl certificate and key directory
# (we don't want any keys in this repository)
VOLUME /etc/ssl/private

# mountable content
VOLUME /usr/share/nginx/html

CMD ["./entrypoint.sh"]
