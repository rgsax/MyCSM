import time
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.sqla_oauth2 import (
	OAuth2ClientMixin,
	OAuth2AuthorizationCodeMixin,
	OAuth2TokenMixin,
)

db = SQLAlchemy()


class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(50), unique=True)
	username = db.Column(db.String(40), unique=True)
	password = db.Column(db.String(128))
	plan_id = db.Column(db.Integer, db.ForeignKey('plan.id', ondelete='CASCADE'))
	instances = None

	def get_user_id(self):
		return self.id

	def get_instances(self):
		if self.instances is None:
			self.instances = Instance.query.filter_by(user_id=self.id).all()
		
		return self.instances

	def get_plan(self):
		return Plan.query.get(self.plan_id)
	
	def get_instances_plans(self):
		instances = Plan.query.with_entities(Plan.max_instances).all()
		data = [item[0] for item in instances]
		return data
	
	def get_total_spending(self):
		spending = Plan.query.get(self.plan_id).price
		for instance in self.get_instances():
			spending += instance.get_product().price
		
		return spending
	
	def get_active_instances(self):
		active_instances = 0
		for instance in self.get_instances():
			if instance.active_state:
				active_instances += 1
		
		return active_instances
	
	def dict_no_instances(self):
		return {
			'id' : self.id,
			'email' : self.email,
			'username' : self.username,
			'plan' : self.get_plan().dict()
		}
	def dict(self):
		d = self.dict_no_instances()
		d['instances'] = [instance.dict_no_user() for instance in self.get_instances()]

		return d

class Plan(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(20), unique=True)
	price = db.Column(db.Float)
	max_instances = db.Column(db.Integer, nullable=True)

	def dict(self):
		return {
			'id' : self.id,
			'name' : self.name,
			'price' : self.price,
			'max_instances' : self.max_instances
		}

class Product(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(50), unique=True)
	price = db.Column(db.Float)

	def dict(self):
		return {
			'id' : self.id,
			'name' : self.name,
			'price' : self.price
		}

class Instance(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
	name = db.Column(db.String(50))
	ram_usage = db.Column(db.Integer)
	storage_usage =  db.Column(db.Integer)
	active_state = db.Column(db.Boolean)

	def get_product(self):
		return Product.query.get(self.product_id)
	
	def get_user(self):
		return User.query.get(self.user_id)

	def dict_no_user(self):
		return {
			'id' : self.id,
			'product' : self.get_product().dict(),
			'name' : self.name,
			'ram_usage' : self.ram_usage,
			'storage_usage' : self.storage_usage,
			'active_state' : self.active_state
		}
	
	def dict(self):
		d = self.dict_no_user()
		d['user'] = self.get_user().dict_no_instances()
		return d


# OAuth2.0 section

class OAuth2User(db.Model):
	__tablename__ = 'oauth2_user'
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(50), unique=True)
	username = db.Column(db.String(40), unique=True)
	password = db.Column(db.String(128))
	clients = None

	def get_user_id(self):
		return self.id

	def check_password(self, password):
		return password == self.password

	def get_clients(self):
		if self.clients is None:
			self.clients = OAuth2Client.query.filter_by(user_id=self.id).all()
		
		return self.clients

class OAuth2Client(db.Model, OAuth2ClientMixin):
	__tablename__ = 'oauth2_client'

	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('oauth2_user.id', ondelete='CASCADE'))


class OAuth2AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):
	__tablename__ = 'oauth2_code'

	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(
		db.Integer, db.ForeignKey('oauth2_user.id', ondelete='CASCADE'))
	user = db.relationship('OAuth2User')


class OAuth2Token(db.Model, OAuth2TokenMixin):
	__tablename__ = 'oauth2_token'

	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(
		db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
	user = db.relationship('User')
	oauth_user_id = db.Column(db.Integer, db.ForeignKey('oauth2_user.id', ondelete='CASCADE'))

	def is_refresh_token_active(self):
		if self.revoked:
			return False
		expires_at = self.issued_at + self.expires_in * 2
		return expires_at >= time.time()
