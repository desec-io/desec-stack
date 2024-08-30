FROM alpine/git
RUN apk -U add build-base \
    && git clone https://github.com/wolfcw/libfaketime /libfaketime
WORKDIR /libfaketime
RUN git checkout ba9ed5b2898f234cfcefbe5c694b7d89dcec4334 \
    && make \
    && make install

FROM python:3.11-alpine

RUN apk add --no-cache bash curl

COPY --from=0 /usr/local/lib/faketime/libfaketimeMT.so.1 /lib/libfaketime.so
RUN mkdir -p /etc/faketime

RUN mkdir /e2e
WORKDIR /e2e
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY apiwait .
COPY *.py .
COPY ./spec .

CMD ./apiwait 300 && python3 -m pytest -vv .
