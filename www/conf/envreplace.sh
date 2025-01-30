#!/bin/bash

export PROD_ONLY=
if [[ $DESECSTACK_E2E_TEST = "TRUE" ]]
then
    export PROD_ONLY='#'
fi

for file in /etc/nginx/sites-available/*.var; do
    # we only replace occurrences of the variables specified below as first argument
    (envsubst '$DESECSTACK_IPV4_REAR_PREFIX16' |
    envsubst '$DESECSTACK_DOMAIN' |
    envsubst '$CERT_PATH' |
    envsubst '$PROD_ONLY' ) < "$file" > $(dirname "$file")/$(basename "$file" .var)
done
