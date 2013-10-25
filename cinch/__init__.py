import os

from flask import Flask
from flask.ext.admin import Admin
from flask.ext.sqlalchemy import SQLAlchemy


GITHUB_CONF = {}
GITHUB_KEYS = [
    'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET', 'GITHUB_CALLBACK_URL',
]
for key in GITHUB_KEYS:
    GITHUB_CONF[key] = os.environ[key]


app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/cinch'
for key, value in GITHUB_CONF.items():
    app.config[key] = value
app.secret_key = '***REMOVED***'

db = SQLAlchemy(app)

admin = Admin(app)

import cinch.views
import cinch.auth.views
import cinch.github
