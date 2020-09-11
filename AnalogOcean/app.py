from website.app import create_app
from flask_talisman import Talisman
from os import environ


app = create_app({
	'SECRET_KEY': 'secret',
	'OAUTH2_REFRESH_TOKEN_GENERATOR': True,
	'SQLALCHEMY_TRACK_MODIFICATIONS': False,
	'SQLALCHEMY_DATABASE_URI': 'sqlite:///db.sqlite',
})

Talisman(
	app,
	content_security_policy = {
    'default-src': [
        '\'self\'',
        '\'unsafe-inline\'',
        'stackpath.bootstrapcdn.com',
        'code.jquery.com',
        'cdn.jsdelivr.net',
		'fonts.googleapis.com',
		'fonts.gstatic.com'
    ]
}) # Flask extension for http security headers

# for https use flask run --cert=cert.pem --key=key.pem
# or uncomment below
if __name__ == "__main__":
	app.run(host='analogocean', ssl_context=(f"{environ['APP_BASE_DIR']}/cert.pem",f"{environ['APP_BASE_DIR']}/key.pem"), port=8888)