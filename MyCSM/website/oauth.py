from authlib.integrations.flask_client import OAuth

def register_oauth_client(client, name):
	return oauth.register(
		name=name + '_' + client.scope,
		client_id=client.client_id,
		client_secret=client.client_secret,
		authorize_url=client.authorization_endpoint,
		access_token_url=client.token_endpoint,
		api_base_url=client.api_endpoint,
		client_kwargs={'scope': client.scope}
	)

oauth = OAuth()
