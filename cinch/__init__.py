from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

try:
    from local_settings import (
        GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_CALLBACK_URL)
except ImportError:
    raise Exception('create a local_settings.py defining '
                    'GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET and '
                    'GITHUB_CALLBACK_URL for Cinch.')

app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/cinch'
app.config['GITHUB_CLIENT_ID'] = GITHUB_CLIENT_ID
app.config['GITHUB_CLIENT_SECRET'] = GITHUB_CLIENT_SECRET
app.config['GITHUB_CALLBACK_URL'] = GITHUB_CALLBACK_URL
app.secret_key = '***REMOVED***'

db = SQLAlchemy(app)

import cinch.views
import cinch.auth.views
