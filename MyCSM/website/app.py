import os
from flask import Flask
from .models import db, CloudServiceProvider, OAuth2Client, Plan
from .routes import bp
from .oauth import oauth, register_oauth_client


def create_app(config=None):
	app = Flask(__name__)

	# load default configuration
	app.config.from_object('website.settings')

	# load environment configuration
	if 'WEBSITE_CONF' in os.environ:
		app.config.from_envvar('WEBSITE_CONF')

	# load app specified configuration
	if config is not None:
		if isinstance(config, dict):
			app.config.update(config)
		elif config.endswith('.py'):
			app.config.from_pyfile(config)

	setup_app(app)
	return app

def setup_app(app):
	# Create tables if they do not exist already
	@app.before_first_request
	def create_tables():
		db.create_all()
		
		if len(Plan.query.all()) == 0:
			db.session.add(Plan(name='free', price=0.0, oauth2_scopes={}))
			db.session.add(Plan(name='premium', price=100.0, oauth2_scopes={}))
			db.session.commit()

	@app.before_first_request
	def register_oauth_clients():
		for client in OAuth2Client.query.all():
			csp = CloudServiceProvider.query.get(client.csp_id)
			register_oauth_client(client, csp.name)
			register_oauth_client(client, csp.name)

	db.init_app(app)
	oauth.init_app(app)
	app.register_blueprint(bp, url_prefix='')
