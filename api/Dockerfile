FROM python:3.10-alpine

COPY --from=trajano/alpine-libfaketime /faketime.so /lib/libfaketime.so
RUN mkdir -p /etc/faketime

RUN apk add --no-cache bash dcron postgresql-client sqlite

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt /usr/src/app/
# freetype-dev is needed for captcha generation
RUN apk add --no-cache gcc freetype-dev libffi-dev musl-dev libmemcached-dev postgresql-dev jpeg-dev zlib-dev git \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip freeze

RUN mkdir /root/cronhook
ADD ["cronhook/crontab", "cronhook/start-cron.sh", "/root/cronhook/"]

RUN crontab /root/cronhook/crontab
RUN chmod +x /root/cronhook/start-cron.sh

RUN mkdir /zones /var/run/celerybeat-schedule \
    && chown nobody /zones /var/run/celerybeat-schedule \
    && chmod 755 /zones \
    && chmod 700 /var/run/celerybeat-schedule

COPY . /usr/src/app

EXPOSE 8000
CMD ["./entrypoint.sh"]
