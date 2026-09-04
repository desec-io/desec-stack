FROM python:3.13-alpine

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

COPY . /usr/src/app

EXPOSE 8000
USER nobody
CMD ["python3", "-u", "arbiter.py"]
