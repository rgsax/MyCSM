import os
from flask import Flask
from .models import db, Plan, Product
from .oauth2 import config_oauth
from .routes import bp


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

def add_initial_values():
	if len(Plan.query.all()) == 0:
		db.session.add(Plan(name='free', price=0, max_instances=3))
		db.session.add(Plan(name='base', price=500, max_instances=10))
		db.session.add(Plan(name='premium', price=100)) # null value for max_instances means infinite instances
		db.session.commit()

	if len(Product.query.all()) == 0:
		db.session.add(Product(name='Virtual Machine', price=100))
		db.session.add(Product(name='Database', price=30))
		db.session.add(Product(name='Mailserver', price=50))
		db.session.commit()


def setup_app(app):
	# Create tables if they do not exist already
	@app.before_first_request
	def create_tables():
		db.create_all()
		add_initial_values()

	db.init_app(app)
	config_oauth(app)
	app.register_blueprint(bp, url_prefix='')
