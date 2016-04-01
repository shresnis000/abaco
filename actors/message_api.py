
from flask import Flask
from request_utils import AbacoApi

from auth import authn_and_authz
from messages import MessagesResource

app = Flask(__name__)
api = AbacoApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()

import logs
app.logger.addHandler(logs.get_file_handler('message_api_logs'))


# Resources
api.add_resource(MessagesResource, '/actors/<string:actor_id>/messages')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
