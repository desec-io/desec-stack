FROM node:8

RUN apt-get update && apt-get install -y \
		dnsutils \
		net-tools \
		dirmngr gnupg \
	--no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN npm install -g chakram mocha

RUN mkdir /usr/src/app
WORKDIR /usr/src/app

COPY ./package.json ./
RUN npm install

COPY *.js ./
COPY ./spec ./spec
COPY ./apiwait ./apiwait

CMD ./apiwait 45 && mocha ./spec
