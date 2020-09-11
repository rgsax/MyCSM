from authlib.integrations.requests_client import OAuth2Session

class CSPClient:
	def __init__(self, client_id, client_secret, scope, cacert, base_url, api_endpoint='api', authorization_endpoint='authorize', token_endpoint='token'):
		self.client_id = client_id
		self.client_secret = client_secret
		self.scope = scope
		self.cacert = cacert
		self.base_url = base_url
		self.api_endpoint = base_url + '/' + api_endpoint
		self.authorization_endpoint = base_url + '/' + authorization_endpoint
		self.token_endpoint = base_url + '/' + token_endpoint
		
		self.client = OAuth2Session(client_id, client_secret, scope=scope)
		self.authorization_url, self.state = self.client.create_authorization_url(self.authorization_endpoint)
		self.token = None

	def request_token(self, authorization_response):
		self.token = self.client.fetch_token(self.token_endpoint, authorization_response=authorization_response, verify=self.cacert) # verify will be passed as argument for the object response, since self signed certificate are not trusted
		return self.token is not None
	
	def get_authorization_url(self):
		return self.authorization_url

	def get(self, api_request, params):
		resp = self.client.get(self.api_endpoint + '/' + api_request, params=params)
		return resp
	
	def post(self, api_request, params):
		resp = self.client.post(self.api_endpoint + '/' + api_request, data=params, verify=self.cacert)
		return resp