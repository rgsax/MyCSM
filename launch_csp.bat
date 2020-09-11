set APP_BASE_DIR=%cd%\%1
set REQUESTS_CA_BUNDLE=%cd%\nostra_app\cert.pem
set FLASK_ENV=development

echo starting

python %1/app.py