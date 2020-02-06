#!/bin/bash

# https://stackoverflow.com/questions/59895/can-a-bash-script-tell-which-directory-it-is-stored-in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export PROD_ONLY=
if [[ $DESECSTACK_E2E_TEST = "TRUE" ]]
then
    export PROD_ONLY='#'
fi

for file in $DIR/*.var; do
    # we only replace occurances of the variables specified below as first argument
    (envsubst '$DESECSTACK_IPV4_REAR_PREFIX16' | envsubst '$DESECSTACK_DOMAIN' | envsubst '$CERT_PATH' | envsubst '$PROD_ONLY' ) < $file > $DIR/`basename $file .var`
done
