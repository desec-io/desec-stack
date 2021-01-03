FROM alpine:latest

RUN apk add --no-cache openssh git python3

RUN adduser -D -s /usr/bin/git-shell git \
  && mkdir /home/git/.ssh \
  && ln -s /etc/ssh/keys/git_authorized_keys /home/git/.ssh/authorized_keys

COPY git-shell-commands /home/git/
COPY sshd_config /etc/ssh/
COPY entrypoint.sh auth /usr/local/bin/

ENTRYPOINT entrypoint.sh
