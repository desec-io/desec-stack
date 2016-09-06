FROM python:2.7

RUN apt-get update && apt-get install -y \
		gcc \
		gettext \
		mysql-client libmysqlclient-dev \
		postgresql-client libpq-dev \
		sqlite3 \
	--no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app
RUN set -ex && \
	rm -f desecapi/settings_local.py && \
	ln -s /usr/src/app/desecapi/hooks/mock/domain_post_create.sh /usr/local/bin && \
	ln -s /usr/src/app/desecapi/hooks/mock/domain_post_update.sh /usr/local/bin

VOLUME /usr/src/app/desecapi/settings_local.py

EXPOSE 8000
CMD ["./entrypoint.sh"]
