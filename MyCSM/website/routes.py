import time
from hashlib import sha3_512
from flask import Blueprint, request, session, url_for
from flask import render_template, redirect, make_response, jsonify
from werkzeug.security import gen_salt
from .models import db, User, Plan, Oauth2Token, CloudServiceProvider, OAuth2Client
from .oauth import oauth, register_oauth_client
from authlib.common.encoding import json_dumps, json_loads
from secrets import token_hex
import sys
import datetime
import requests

bp = Blueprint(__name__, 'home')

def current_user():
	if 'id' in session:
		uid = session['id']
		return User.query.get(uid)
	return None

@bp.route('/administration', methods=['GET'])
def administration():
	plans = [(plan.id, plan.name) for plan in Plan.query.all()]
	csps = [(csp.id, csp.name) for csp in CloudServiceProvider.query.all()]
	return render_template('register_csp.html', plans=plans, csps=csps)

# Register a new OAuth2 client for a csp
# and define a scope for the specified plan 
@bp.route('/administration/register_csp', methods=['POST'])
def register_csp():
	csp = CloudServiceProvider.query.get(request.form.get('csp', type=int))
	scope = request.form.get('scope')
	client = OAuth2Client(
		csp_id=csp.id,
		scope=scope,
		client_id=request.form.get('client_id'),
		client_secret=request.form.get('client_secret'),
		authorization_endpoint=request.form.get('authorization_endpoint'),
		token_endpoint=request.form.get('token_endpoint'),
		api_endpoint=request.form.get('api_endpoint'),
		revoke_endpoint=request.form.get('revoke_endpoint')
	)

	plan = Plan.query.get(request.form.get('plan', type=int))
	plan.add_scope(csp.name, scope)
	db.session.add(client)
	db.session.commit()

	register_oauth_client(client, csp.name)

	return redirect('/administration')


@bp.route('/index')
@bp.route('/', methods=('GET', 'POST'))
def home():
	if request.method == 'POST':
		email = request.form.get('email')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		user = User.query.filter_by(email=email, password=pwd_hash).first()
		if not user:
			return render_template('login.html', message="Login failed")
		session['id'] = user.id
		return redirect('/')
	
	user = current_user()
	if user:
		clouds = []
		user_csps = []
		tot_exp = 0
		
		for csp in CloudServiceProvider.query.all():
			clouds.append((csp.id, csp.name))
			if OAuth2Client.query.filter_by(csp_id=csp.id).join(Oauth2Token, OAuth2Client.id==Oauth2Token.client_id).filter_by(user_id=user.id).first():
				user_csps.append((csp.id, csp.name))
				tot_exp+=float(get_user_spendings(csp.name, user))
	
		plans = [(plan.price) for plan in  Plan.query.all()]
		return render_template('index.html', user=user,clouds=clouds,user_csps=user_csps, tot_exp=tot_exp, plans_available=plans)

	return render_template('login.html')

# The update of the plan cause the deletion of every token of the user
@bp.route('/update_plan',methods=['POST'])
def update_plan():
	user = User.query.get(request.form.get('user_id',type=int))
	if not user:
		return make_response('User not found/logged, please go <a href="https://mycsm:5000">here</a> and try again: ',404)

	for token in Oauth2Token.query.filter_by(user_id=user.id).all():
		client = OAuth2Client.query.get(token.client_id)
		csp = CloudServiceProvider.query.get(client.csp_id)
		remove_csp(csp.name) 

	user.plan_id = request.form.get('plan_id',type=int)
	db.session.commit()
	return redirect('/')

# This route retrieves and collects the infos of the user for every token 
# associated to its Cloud Service Provider
@bp.route('/user_info')
def user_info():	
	user = current_user()
	if user:
		user_csps = []
		tot_exp = 0

		for csp in CloudServiceProvider.query.all():
			if OAuth2Client.query.filter_by(csp_id=csp.id).join(Oauth2Token, OAuth2Client.id==Oauth2Token.client_id).filter_by(user_id=user.id).first():
				user_csps.append((csp.id, csp.name))
				tot_exp+=float(get_user_spendings(csp.name, user))

		plans = [(plan.price) for plan in  Plan.query.all()]
		return render_template('user.html', user=user,user_csps=user_csps,tot_exp=tot_exp,plans_available=plans)
	else:
		return make_response('User not found/logged, please go <a href="https://mycsm:5000">here</a> and try again: ',404)

# The user is registered saving its username, email, the plan
# and the hash of the password (a strong hash function as SHA3-512 is used) 
@bp.route('/register', methods=('GET', 'POST'))
def register():
	if request.method == 'POST':
		email = request.form.get('email')
		username = request.form.get('username')
		pwd_hash = sha3_512(request.form.get('password').encode()).hexdigest()
		plan = int(request.form.get('plan'))
		new_user = User(email=email, username=username, password=pwd_hash, plan_id=plan, token=token_hex(16))
		db.session.add(new_user)
		db.session.commit()
		session['id'] = new_user.id
		return redirect('/')
	
	plans = [(plan.id, plan.name) for plan in  Plan.query.all()]
	return render_template('register.html', plans=plans)
	
# redirect to the specified Cloud Service Provider dhashboard page (of mycsm)
@bp.route('/csp/<string:name>')
def view_csp(name):	
	user = current_user()
	if not(user):
		return make_response('User not found/logged, please go <a href="https://mycsm:5000">here</a> and try again: ',404)
	else:
		csp = CloudServiceProvider.query.filter_by(name=name).first()
		scope = user.get_plan().get_scope(csp.name)
		user_csps = []
		for csp in CloudServiceProvider.query.all():
			if OAuth2Client.query.filter_by(csp_id=csp.id).join(Oauth2Token, OAuth2Client.id==Oauth2Token.client_id).filter_by(user_id=user.id).first():
				user_csps.append((csp.id, csp.name))
		plans = [(plan.price) for plan in  Plan.query.all()]
		return render_template('csp.html', user=user,user_csps=user_csps,plans_available=plans, user_scope=scope)



@bp.route('/logout')
def logout():
	del session['id']
	return redirect('/')

# This is the callback route to call during the OAuth2 flow for the initial authorization
@bp.route('/callback/<csp>/<scope>', methods=['GET', 'POST'])
def callback(csp, scope):
	db_csp = CloudServiceProvider.query.filter_by(name=csp).first()
	db_client = OAuth2Client.query.filter_by(csp_id=db_csp.id, scope=scope).first()
	client = db_client.get_client()
	token = client.authorize_access_token()
	db.session.add(Oauth2Token(token=json_dumps(token), user_id=current_user().id, client_id=db_client.id))
	db.session.commit()
	session[csp] = scope
	return redirect(f"/csp/{csp}")

# This route is used to authorize MyCSM to access to the user's resources 
# of the specified Cloud Service Provider using OAuth2
@bp.route('/add_csp', methods=['POST'])
def add_csp():
	user = current_user()
	if user:
		csp = CloudServiceProvider.query.get(request.form.get('csp_id', type=int))
		print(csp.name, file=sys.stderr)
		scope = user.get_plan().get_scope(csp.name)
		client = OAuth2Client.query.filter_by(csp_id=csp.id, scope=scope).first().get_client()
		return client.authorize_redirect()

	return make_response(jsonify("{error:'user non found'}"), 200)

# CSP specific APIs

# The following APIs are used as a wrapper for all the Cloud Service Provider APIs.
# Every route calls the CSP specific API using the token received during the OAuth2
# authorization process, and returns the result.

def get_oauth2_client(csp_name, user):
	csp = CloudServiceProvider.query.filter_by(name=csp_name).first()
	user = current_user()
	if not user:
		return render_template('login.html', message="Login failed")
	scope = user.get_plan().get_scope(csp.name)
	client = OAuth2Client.query.filter_by(csp_id=csp.id, scope=scope).first()
	db_token = Oauth2Token.query.filter_by(user_id=user.id, client_id=client.id).first()
	token = json_loads(db_token.token)
	client.token = token
	return client

def get_oauth2_db_token(csp_name, user):
	csp = CloudServiceProvider.query.filter_by(name=csp_name).first()
	user = current_user()
	if not user:
		return render_template('login.html', message="Login failed")
	scope = user.get_plan().get_scope(csp.name)
	client = OAuth2Client.query.filter_by(csp_id=csp.id, scope=scope).first()
	db_token = Oauth2Token.query.filter_by(user_id=user.id, client_id=client.id).first()
	return db_token


@bp.route('/csp/<csp>/remove')
def remove_csp(csp):
	user = current_user()
	if not user:
		return redirect('/')
	
	client = get_oauth2_client(csp, user)
	resp = client.get_client().post('oauth/revoke')
	if resp.status_code == 200:
		db.session.delete(get_oauth2_db_token(csp, user))
		db.session.commit()
		return redirect('/')
	
	return make_response(resp.json(), resp.status_code)

def get_user_spendings(csp, user):
	client = get_oauth2_client(csp, user)	
	resp = client.get_client().get('api/get_user_spendings')
	if resp.status_code != 200:
		raise RuntimeError("status_code != 200")
	return resp.json()['total_spending']

@bp.route('/api/get_user_spendings', methods=['GET'])
def get_user_spending_route():
	csp = request.args.get('csp')	
	user = current_user()
	
	spendings = get_user_spendings(csp, user)
	return make_response(jsonify("{spendings:" + str(spendings) + "}"), 200)

@bp.route('/api/get_products', methods=['GET'])
def get_products():
	user = current_user()
	client = get_oauth2_client(request.args.get('csp'), user)	
	resp = client.get_client().get('api/get_products')
	if resp.status_code == 200:
		return make_response(jsonify(resp.json()), 200)
	return make_response(jsonify(resp.json()), 400)

@bp.route('/api/get_instances', methods=['GET'])
def get_instances():
	user = current_user()
	client = get_oauth2_client(request.args.get('csp'), user)	
	resp = client.get_client().get('api/get_instances')
	if resp.status_code == 200:
		return make_response(jsonify(resp.json()), 200)
	return make_response(jsonify(resp.json()), 400)
	
@bp.route('/api/create_instance', methods=['POST'])
def create_instance():
	client = get_oauth2_client(request.form.get('csp'), current_user())
	myobj = request.form
	resp = client.get_client().post('api/create_instance', data = myobj)
	print(resp.text, file=sys.stderr)
	if resp.status_code == 200:
		return make_response(jsonify(resp.json()), 200)
	return make_response(jsonify(error=str(resp.text)),400)

@bp.route('/api/rename_instance', methods=['POST'])
def rename_instance():
	client = get_oauth2_client(request.form.get('csp'), current_user())
	myobj = request.form
	resp = client.get_client().post('api/rename_instance', data = myobj)

	if resp.status_code == 200:
		return make_response(jsonify(resp.json()), 200)
	return make_response(jsonify('{error:error}', 400))


@bp.route('/api/delete_instance', methods=['POST'])
def delete_instance():
	client = get_oauth2_client(request.form.get('csp'), current_user())
	myobj = request.form
	resp = client.get_client().post('api/delete_instance', data = myobj)

	if resp.status_code == 200:
		return make_response(jsonify(resp.json()))
	return make_response(jsonify('{error:error}', 400))

@bp.route('/api/set_instance_activestate', methods=['POST'])
def set_instance_activestate():
	client = get_oauth2_client(request.form.get('csp'), current_user())
	myobj = request.form
	resp = client.get_client().post('api/set_instance_activestate', data = myobj)

	if resp.status_code == 200:
		#return make_response(jsonify(resp.json()))
		return make_response("risposta da sistemare")
	return make_response(jsonify('{error:error}', 400))