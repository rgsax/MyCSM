#! /bin/sh

export APP_BASE_DIR=$(pwd)/$1
export REQUESTS_CA_BUNDLE=$(pwd)/nostra_app/cert.pem
export FLASK_ENV=development

echo starting

python3 $1/app.py