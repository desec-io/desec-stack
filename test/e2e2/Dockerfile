FROM python:3.8

RUN mkdir /e2e
WORKDIR /e2e
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY apiwait .
COPY *.py .
COPY ./spec .

CMD ./apiwait 45 && python3 -m pytest -vv .
