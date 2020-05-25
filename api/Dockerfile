FROM python:3.8-buster

RUN apt-get update && apt-get install -y \
        # updating this list may require updating /README.md
		gcc \
		gettext \
		default-mysql-client default-libmysqlclient-dev \
		libmemcached-dev \
		postgresql-client libpq-dev \
		sqlite3 \
		cron \
	--no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install -r requirements.txt && rm -rf /root/.cache/
RUN pip freeze

RUN mkdir /root/cronhook
ADD ["cronhook/crontab", "cronhook/start-cron.sh", "/root/cronhook/"]

RUN crontab /root/cronhook/crontab
RUN chmod +x /root/cronhook/start-cron.sh

COPY . /usr/src/app

EXPOSE 8000
CMD ["./entrypoint.sh"]
