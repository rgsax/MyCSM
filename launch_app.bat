set APP_BASE_DIR=%cd%\MyCSM
set REQUESTS_CA_BUNDLE=%cd%\certs.ca-bundle
set FLASK_ENV=development

echo starting

python MyCSM/app.py