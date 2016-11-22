FROM python:latest

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
	rm -f desecapi/settings_local.py

VOLUME /usr/src/app/desecapi/settings_local.py

EXPOSE 8000
CMD ["./entrypoint.sh"]
