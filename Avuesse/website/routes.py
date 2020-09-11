import time
from hashlib import sha3_512
from flask import Blueprint, request, session, url_for
from flask import render_template, redirect, make_response, jsonify
from werkzeug.security import gen_salt
from authlib.integrations.flask_oauth2 import current_token
from authlib.oauth2 import OAuth2Error
from .models import db, User, Plan, Product, Instance, OAuth2User,OAuth2Client, OAuth2Token
from .oauth2 import authorization, require_oauth
import datetime
from random import randint

bp = Blueprint(__name__, 'home')

# useful methods

def current_user():
	if 'id' in session:
		uid = session['id']
		return User.query.get(uid)
	return None

def current_oauth2_user():
	if 'oauth_id' in session:
		uid = session['oauth_id']
		return OAuth2User.query.get(uid)
	return None

def split_by_crlf(s):
	return [v for v in s.splitlines() if v]

# Create an instance related to the specifided product for a certain user
# and assigns a random amount of used storage and RAM
def create_instance(user):
	if not user:
		return make_response(jsonify(error='user not found'), 404)
	
	if can_create_instance(user):
		instance = Instance(
			product_id = request.form.get('instance_productid', type=int),
			user_id = user.id,
			name = request.form.get('instance_name', type=str),
			ram_usage = randint(0, 100),
			storage_usage = randint(0, 100),
			active_state = True
		)
		db.session.add(instance)
		db.session.commit()
		
		return f"{instance.id}"
	return make_response(jsonify(error="Cannot create new instance, Instance limit reached"),403)

# A user can create an instance only if it has a premium plan 
# (max instances = None is used to say that there is no limit to the number of instances)
# or the number of the current instances is less than max_instances related to the plan
def can_create_instance(user):
	return user.get_plan().max_instances is None or len(user.get_instances()) < user.get_plan().max_instances

# Delete an instance of a certain user
def delete_instance(user):
	if not user:
		return make_response(jsonify(error='user not found'), 404)
	instance = Instance.query.get(request.form.get('instance_id', type=int))

	if not instance:
		return make_response(jsonify(error="instance not found"), 404)

	db.session.delete(instance)
	db.session.commit()
	return make_response(jsonify(success="instance deleted"), 200)

# Rename an instance of a certain user
def rename_instance(user):
	if not user:
		return make_response(jsonify(error='user not found'), 404)

	instance = Instance.query.get(request.form.get('instance_id', type=int))
	if not instance:
		return make_response(jsonify(error="instance not found"), 404)

	instance.name = request.form.get('instance_name', type=str)

	db.session.commit()
	return make_response(jsonify(instance.dict_no_user(), 200))

# Set the state of an instance (belonging to a certain user) to active (True)
# or not active (False)
def set_instance_activestate(user):
	if not user:
		return make_response(jsonify(error='user not found'), 404)

	instance = Instance.query.get(request.form.get('instance_id', type=int))
	if not instance:
		return make_response(jsonify(error="instance not found"), 404)

	instance.active_state = request.form.get('instance_activestate') == 'true'

	db.session.commit()
	return make_response(jsonify(instance.dict_no_user(), 200))

# routes

@bp.app_template_filter()
def pretty_date(dttm):
    return datetime.datetime.fromtimestamp(dttm).strftime('%Y-%m-%d')

@bp.route('/', methods=('GET', 'POST'))
def home():
	if request.method == 'POST':
		email = request.form.get('email')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		user = User.query.filter_by(email=email, password=pwd_hash).first()
		if not user:
			return render_template('login.html', message="Login failed")
		session['id'] = user.id

		# if user is not just to log in, but need to head back to the auth page, then go for it
		next_page = request.args.get('next')
		if next_page:
			return redirect(next_page)

		return redirect('/')
	user = current_user()
	if user:
		plan = user.get_plan()
		plans = [(plan.price) for plan in  Plan.query.all()]
		plan_n_instances = user.get_instances_plans()
		plan= user.get_plan()
		s = user.get_total_spending() # spending_monthly
		active_instances = user.get_active_instances()
		products= Product.query.all()
		return render_template('index.html', user=user, products=products, n_plans_instance=plan_n_instances, plans_available=plans, max_instances=plan.max_instances, spending_mounthly=s, active_instances=active_instances)

	return render_template('login.html')


# The user is registered saving its username, email, the plan
# and the hash of the password (a strong hash function as SHA3-512 is used) 
@bp.route('/register', methods=('GET', 'POST'))
def register():
	if request.method == 'POST':
		email = request.form.get('email')
		username = request.form.get('username')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		plan = int(request.form.get('plan'))
		new_user = User(email=email, username=username, password=pwd_hash, plan_id=plan)
		db.session.add(new_user)
		db.session.commit()
		session['id'] = new_user.id
		return redirect('/')
	
	plans = [(plan.id, plan.name) for plan in  Plan.query.all()]
	return render_template('register.html', plans=plans)
	

@bp.route('/logout')
def logout():
	del session['id']
	return redirect('/')

# OAuth2.0 section

# The page 'endpoints.html' contains all the oauth endpoints related to the csp,
# including the API endpoint
@bp.route('/oauth/endpoints', methods=['GET'])
def show_endpoints():
	oauth2_user = current_oauth2_user()
	if not oauth2_user:
		return redirect('/oauth')
	return render_template('endpoints.html')

@bp.route('/oauth/home', methods=['GET'])
def show_home():
	oauth2_user = current_oauth2_user()
	if not oauth2_user:
		return redirect('/oauth')
	
	clients = oauth2_user.get_clients()
	return render_template('home.html', user=oauth2_user, clients=clients)

# Register an OAuth2 user account that gives the possibility to create clients
# fro accessing APIs
@bp.route('/oauth/register', methods=('GET', 'POST'))
def oauth_register():
	if request.method == 'POST':
		email = request.form.get('email')
		username = request.form.get('username')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		new_oauth2_user = OAuth2User(email=email, username=username, password=pwd_hash)
		db.session.add(new_oauth2_user)
		db.session.commit()
		session['oauth_id'] = new_oauth2_user.id
		return redirect('/oauth')
	
	return render_template('register_oauth.html')

@bp.route('/oauth', methods=('GET', 'POST'))
def oauth_home():
	if request.method == 'POST':
		email = request.form.get('email')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		oauth2_user = OAuth2User.query.filter_by(email=email, password=pwd_hash).first()
		if not oauth2_user:
			return render_template('login_oauth.html', message="Login failed")
		
		session['oauth_id'] = oauth2_user.id
		return redirect('/oauth')
	oauth2_user = current_oauth2_user()
	if oauth2_user:
		return render_template('administration.html',user=oauth2_user)

	return render_template('login_oauth.html')


@bp.route('/oauth/logout')
def oauth_logout():
	del session['oauth_id']
	return redirect('/oauth')

# Create an OAuth2 client generating a client_id and a client_secret
# that will be used in the authorization flow to obtain the corresponding
# token, based on the requested scope
@bp.route('/oauth/create_client', methods=('GET', 'POST'))
def create_client():
	user = current_oauth2_user()
	if not user:
		return redirect('/oauth')
	if request.method == 'GET':
		return render_template('create_client.html')

	client_id = gen_salt(24)
	client_id_issued_at = int(time.time())
	client = OAuth2Client(
		client_id=client_id,
		client_id_issued_at=client_id_issued_at,
		user_id=user.id,
	)

	form = request.form
	client_metadata = {
		"client_name": form["client_name"],
		"client_uri": form["client_uri"],
		"grant_types": split_by_crlf(form["grant_type"]),
		"redirect_uris": split_by_crlf(form["redirect_uri"]),
		"response_types": split_by_crlf(form["response_type"]),
		"scope": form["scope"],
		"token_endpoint_auth_method": form["token_endpoint_auth_method"]
	}
	client.set_client_metadata(client_metadata)

	if form['token_endpoint_auth_method'] == 'none':
		client.client_secret = ''
	else:
		client.client_secret = gen_salt(48)

	db.session.add(client)
	db.session.commit()
	return redirect('/oauth')


# Authorization step of the OAuth2 flow
@bp.route('/oauth/authorize', methods=['GET', 'POST'])
def authorize():
	user = current_user()
	# if user log status is not true (Auth server), then to log it in
	if not user:
		return redirect(url_for('website.routes.home', next=request.url))
	if request.method == 'GET':
		try:
			grant = authorization.validate_consent_request(end_user=user)
		except OAuth2Error as error:
			return error.error
		return render_template('authorize.html', user=user, grant=grant)
	if not user and 'username' in request.form:
		username = request.form.get('username')
		user = User.query.filter_by(username=username).first()
	if request.form['confirm']:
		grant_user = user
	else:
		grant_user = None
	return authorization.create_authorization_response(grant_user=grant_user)

@bp.route('/oauth/delete_client', methods=['POST'])
def delete_client():
	client = OAuth2Client.query.get(request.form.get('oauth2_id', type=int))
	if not client:
		return make_response('client does not exist', 403)
	if 'oauth_id' in session:
		db.session.delete(client)
		db.session.commit()
		return ''
	return make_response('', 405)

# Create a token for the client that passed the OAuth2 authorization step
@bp.route('/oauth/token', methods=['POST'])
def issue_token():
	return authorization.create_token_response()

# Revoke the OAuth2 token for a certain client
@bp.route('/oauth/revoke', methods=['POST'])
@require_oauth(['read', 'write'], operator='OR')
def revoke_token():
	user = current_token.user
	if user:
		token = OAuth2Token.query.filter_by(user_id=user.id).first()
		db.session.delete(token)
		db.session.commit()
		return make_response(jsonify("{success:success}"), 200)
	return make_response(jsonify("{error:'internal server error'}"), 500)

# internal API section

@bp.route('/create_instance', methods=['POST'])
def create_instance_route():
	user = current_user()
	return create_instance(user)

@bp.route('/delete_instance', methods=['POST'])
def delete_instance_route():
	user = current_user()
	return delete_instance(user)

@bp.route('/rename_instance', methods=['GET', 'POST'])
def rename_instance_route():
	user = current_user()
	return rename_instance(user)

@bp.route('/set_instance_activestate', methods=['POST'])
def set_instance_activestate_route():
	user = current_user()
	return set_instance_activestate(user)

@bp.route('/update_plan',methods=['POST'])
def update_plan():
	user = User.query.get(request.form.get('user_id',type=int))
	if not user:
		return make_response(jsonify(error="user not found"),404)

	user.plan_id = request.form.get('plan_id',type=int)
	db.session.commit()
	return make_response(jsonify(success="plan updated"), 200)

# Non OAuth2 API section

@bp.route('/api/get_products', methods=['GET'])
def get_products_api():
	return make_response(jsonify(list(map(lambda product: product.dict(), Product.query.all()))), 200)

# OAuth2 API section

# All of theese APIs can be accessed only with an OAuth2 authorization.
# Every API is binded to a scope (or multiple scopes, that will be requested together or spearately)
# that limits the access only to those token wich are associated with the right scope

@bp.route('/api/create_instance', methods=['POST'])
@require_oauth('write')
def create_instance_api():
	user = current_token.user
	return create_instance(user)

@bp.route('/api/delete_instance', methods=['POST'])
@require_oauth('write')
def delete_instance_api():
	user = current_token.user
	return delete_instance(user)

@bp.route('/api/rename_instance', methods=['GET', 'POST'])
@require_oauth('write')
def rename_instance_api():
	user = current_token.user
	return rename_instance(user)

@bp.route('/api/set_instance_activestate', methods=['POST'])
@require_oauth(['read', 'write'], operator='OR')
def set_instance_activestate_api():
	user = current_token.user
	return set_instance_activestate(user)

@bp.route('/api/get_user_spendings', methods=['GET'])
@require_oauth(['read', 'write'], operator='OR')
def get_user_spendings():
	user = current_token.user
	if not user:
		return make_response(jsonify(error="user not found"), 404)
	
	return make_response(jsonify(total_spending=user.get_total_spending()), 200)

@bp.route('/api/get_instances', methods=['GET'])
@require_oauth(['read', 'write'], operator='OR')
def get_user_instances():
	user = current_token.user
	if not user:
		return make_response(jsonify(error="user not found"), 404)
	
	return make_response(jsonify([instance.dict() for instance in user.get_instances()]), 200)

@bp.route('/api/get_user_info', methods=['GET'])
@require_oauth(['read', 'write'], operator='OR')
def get_user_info():
	user = current_token.user
	if not user:
		return make_response(jsonify(error="user not found"), 404)
	
	return make_response(jsonify(user.dict()), 200)