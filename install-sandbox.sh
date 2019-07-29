#!/usr/bin/env bash
set -e

# check prerequisites for installing the sandbox
check() {
  # must run as root
  [[ $(id -u) == 0 ]] || (echo "Must run as root."; exit 1)

  # must have environment variables set up
  [[ -n "${DOMAIN}" ]] || (echo "Please set DOMAIN so we can use desec.\$DOMAIN and {ns1,ns2}.\$DOMAIN as hostnames."; exit 1)
  [[ -n "${IP4_BACKEND}" ]] || (echo "Please set IP4_BACKEND."; exit 1)
  [[ -n "${IP4_NS1}" ]] || (echo "Please set IP4_NS1."; exit 1)
  [[ -n "${IP4_NS2}" ]] || (echo "Please set IP4_NS2."; exit 1)
  [[ -n "${EMAIL}" ]] || (echo "Please set EMAIL (for LE cert)."; exit 1)
  [[ -n "${TOKEN}" ]] || (echo "Please set TOKEN to an access token for the deSEC.io account controlling the sandbox domain."; exit 1)
}

# helper functions
rand() {
  openssl rand -base64 32
}

# set up host
setup() {
  # make sure apt ist up-to-date
  apt update

  # set up Nils' favorite shell environment: ohmyzsh
  apt install -y zsh
  chsh -s "$(command -v zsh)"

  wget https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh
  rm -rf .oh-my-zsh
  sh install.sh --unattended
  wget -O .oh-my-zsh/themes/agnoster.zsh-theme https://raw.githubusercontent.com/agnoster/agnoster-zsh-theme/master/agnoster.zsh-theme
  cat > .zshrc << EOF
export ZSH="/root/.oh-my-zsh"
ZSH_THEME="agnoster"
plugins=(git)
source \$ZSH/oh-my-zsh.sh
prompt_lab() {
  prompt_segment 'black' 'default' '🧪'
}
AGNOSTER_PROMPT_SEGMENTS=("prompt_lab" "\${AGNOSTER_PROMPT_SEGMENTS[@]}")
AGNOSTER_PROMPT_SEGMENTS[3]=
EOF

  # install dependencies
  apt install -y \
    curl \
    git \
    httpie \
    jq \
    libmysqlclient-dev \
    python3.7-dev \
    python3.7-venv \
    docker.io \
    docker-compose \
    certbot \

}

dns() {
  # TODO add v6
  http PUT https://desec.io/api/v1/domains/${DOMAIN}/rrsets/ Authorization:"Token ${TOKEN}" << EOF
[
    {"type": "A",    "ttl":300, "records": ["$IP4_NS1"], "subname": "ns1"},
    {"type": "A",    "ttl":300, "records": ["$IP4_NS2"], "subname": "ns2"},
    {"type": "A",    "ttl":300, "records": ["$IP4_BACKEND"], "subname": "desec"},
    {"type": "A",    "ttl":300, "records": ["$IP4_BACKEND"], "subname": "dedyn"},
    {"type": "A",    "ttl":300, "records": ["$IP4_BACKEND"], "subname": "*.desec"}
]
EOF
}

backend() {
  # get desec-stack
  git clone https://github.com/desec-io/desec-stack.git
  rm -rf desec-stack/certs
  mv certs desec-stack/
  cd desec-stack || exit

  # set up environment
  touch .env
  cat >> .env << EOF
DESECSTACK_DOMAIN=$DOMAIN
DESECSTACK_NS=ns1.$DOMAIN ns2.$DOMAIN
DESECSTACK_IPV4_REAR_PREFIX16=172.16
DESECSTACK_IPV6_SUBNET=fda8:7213:9e5e:1::/80
DESECSTACK_IPV6_ADDRESS=fda8:7213:9e5e:1::0642:ac10:0080
DESECSTACK_WWW_CERTS=./certs
DESECSTACK_DBMASTER_CERTS=./certs
DESECSTACK_API_ADMIN=$EMAIL
DESECSTACK_API_SEPA_CREDITOR_ID=SANDBOX_SEPA_CREDITOR_ID
DESECSTACK_API_SEPA_CREDITOR_NAME=SANDBOX_SEPA_CREDITOR_NAME
DESECSTACK_API_EMAIL_HOST=
DESECSTACK_API_EMAIL_HOST_USER=
DESECSTACK_API_EMAIL_HOST_PASSWORD=
DESECSTACK_API_EMAIL_PORT=
DESECSTACK_API_SECRETKEY=$(rand)
DESECSTACK_API_PSL_RESOLVER=9.9.9.9
DESECSTACK_DBAPI_PASSWORD_desec=$(rand)
DESECSTACK_MINIMUM_TTL_DEFAULT=1
DESECSTACK_NORECAPTCHA_SITE_KEY=
DESECSTACK_NORECAPTCHA_SECRET_KEY=
DESECSTACK_DBLORD_PASSWORD_pdns=$(rand)
DESECSTACK_NSLORD_APIKEY=$(rand)
DESECSTACK_NSLORD_CARBONSERVER=
DESECSTACK_NSLORD_CARBONOURNAME=
DESECSTACK_NSLORD_DEFAULT_TTL=3600
DESECSTACK_DBMASTER_PASSWORD_pdns=$(rand)
DESECSTACK_DBMASTER_PASSWORD_replication_manager=$(rand)
DESECSTACK_NSMASTER_APIKEY=$(rand)
DESECSTACK_NSMASTER_CARBONSERVER=37.252.122.50
DESECSTACK_NSMASTER_CARBONOURNAME=$DOMAIN
DESECSTACK_REPLICATION_MANAGER_CERTS=./replication-certs
EOF

  # mock static files  # TODO add the real thing
  rm static
  mkdir static
  cat > static/index.html << EOF
<h1>deSEC Stack Sandbox</h1>
<p>This sandbox is for testing purposes. Please do not use it in production.</p>
<p>The API can be found at <a href="/api/v1/">/api/v1/</a>.</p>
EOF
  cat > static/Dockerfile << EOF
FROM nginx:stable
COPY index.html /usr/share/nginx/html/index.html
EOF
}

frontend() {
  # get desec-stack
  git clone https://github.com/desec-io/desec-slave.git
  cd desec-slave || exit
}

certs() {
  (
    mkdir -p ~/bin
    cd ~/bin
    curl https://raw.githubusercontent.com/desec-utils/certbot-hook/master/hook.sh > desec_certbot_hook.sh
    chmod +x desec_certbot_hook.sh
    cd
    touch .dedynauth; chmod 600 .dedynauth
    echo DEDYN_TOKEN=${TOKEN} >> .dedynauth
    echo DEDYN_NAME=${DOMAIN} >> .dedynauth
  )
  (
    cd
    certbot \
      --config-dir certbot/config --logs-dir certbot/logs --work-dir certbot/work \
      --manual --text --preferred-challenges dns \
      --manual-auth-hook ~/bin/desec_certbot_hook.sh \
      --server https://acme-v02.api.letsencrypt.org/directory \
      --non-interactive --manual-public-ip-logging-ok --agree-tos --email "$EMAIL" \
      -d "*.${DOMAIN}" certonly
  )
  (
    mkdir -p certs
    cd certs
    for SUBNAME in desec www.desec get.desec checkip.dedyn checkipv4.dedyn checkipv6.dedyn dedyn www.dedyn update.dedyn update6.dedyn
    do
        ln -s cer ${SUBNAME}.${DOMAIN}.cer
        ln -s key ${SUBNAME}.${DOMAIN}.key
    done

    cp ~/certbot/config/live/${DOMAIN}/fullchain.pem cer
    cp ~/certbot/config/live/${DOMAIN}/privkey.pem key
  )
}

case $1 in
  frontend) check && setup && frontend ;;
  backend) check && setup && dns && certs && backend ;;
  *) echo "usage: ./install-sandbox.sh [frontend|backend]"; exit 1 ;;
esac
