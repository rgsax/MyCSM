from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from authlib.common.encoding import json_loads, json_dumps
from .oauth import oauth, register_oauth_client

db = SQLAlchemy()

class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(50), unique=True)
	username = db.Column(db.String(40), unique=True)
	password = db.Column(db.String(128))
	plan_id = db.Column(db.Integer, db.ForeignKey('plan.id', ondelete='CASCADE'))
	token = db.Column(db.String(16))

	def get_plan(self):
		return Plan.query.get(self.plan_id)

	def get_token(self):
		return self.token


class Plan(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(20), unique=True)
	price = db.Column(db.Float)
	oauth2_scopes = db.Column(db.Text) # it will be a dictionary { csp : scope, ... }

	def get_scope(self, csp):
		return json_loads(self.oauth2_scopes)[csp]
	
	def add_scope(self, csp, scope):
		scopes = json_loads(self.oauth2_scopes)
		scopes[csp] = scope
		self.oauth2_scopes = json_dumps(scopes)


class CloudServiceProvider(db.Model):
	__tablename__ = 'cloud_service_provider'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(20), unique=True)

class OAuth2Client(db.Model):
	__tablename__ = "oauth2_client"
	id = db.Column(db.Integer, primary_key=True)
	csp_id = db.Column(db.Integer, db.ForeignKey('cloud_service_provider.id', ondelete='CASCADE'))
	scope = db.Column(db.String(10))
	client_id = db.Column(db.String(24), unique=True)
	client_secret = db.Column(db.String(48))
	api_endpoint = db.Column(db.String(10))
	authorization_endpoint = db.Column(db.String(10))
	token_endpoint = db.Column(db.String(10))
	revoke_endpoint = db.Column(db.String(10))
	
	def get_client(self):
		csp = CloudServiceProvider.query.get(self.csp_id)
		client = oauth.create_client(csp.name + "_" + self.scope)
		if not client:
			client = register_oauth_client(self, csp.name)

		db_token = Oauth2Token.query.filter_by(client_id=self.id).first()
		if db_token:
			client.token = json_loads(db_token.token)
		return client


class Oauth2Token(db.Model):
	__tablename__ = "oauth2_token"
	token = db.Column(db.Text, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
	client_id = db.Column(db.Integer, db.ForeignKey('oauth2_client.id', ondelete='CASCADE'))