#! /bin/sh

export APP_BASE_DIR=$(pwd)/MyCSM
export REQUESTS_CA_BUNDLE=$(pwd)/certs.ca-bundle
export FLASK_ENV=development

echo starting

python3 MyCSM/app.py