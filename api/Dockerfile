FROM python:3.8-alpine

RUN apk add --no-cache bash dcron postgresql-client sqlite

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt /usr/src/app/
RUN apk add --no-cache gcc freetype-dev libffi-dev musl-dev libmemcached-dev postgresql-dev jpeg-dev zlib-dev \
    && pip install -r requirements.txt \
    && apk --no-cache del gcc
RUN pip freeze

RUN mkdir /root/cronhook
ADD ["cronhook/crontab", "cronhook/start-cron.sh", "/root/cronhook/"]

RUN crontab /root/cronhook/crontab
RUN chmod +x /root/cronhook/start-cron.sh

COPY . /usr/src/app

EXPOSE 8000
CMD ["./entrypoint.sh"]
