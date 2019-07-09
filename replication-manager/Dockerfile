FROM python:3-alpine

WORKDIR /usr/src/app
COPY requirements.txt ./

RUN apk add --no-cache build-base && \
    apk add --no-cache gcc musl-dev python3-dev libffi-dev openssl-dev && \
    apk add --no-cache mariadb-connector-c-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev python3-dev libffi-dev openssl-dev && \
    apk del build-base

COPY . .

ENTRYPOINT [ "python", "./replication-manager.py" ]
