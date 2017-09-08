#!/bin/bash

# replace environment references in config files
./etc/nginx/sites-available/envreplace.sh

nginx -g "daemon off;"
