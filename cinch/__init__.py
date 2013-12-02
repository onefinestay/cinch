import os

from flask import Flask
from flask.ext.admin import Admin
from flask.ext.sqlalchemy import SQLAlchemy
from raven.contrib.flask import Sentry


DEFAULT_DB_URI = 'sqlite://'


app = Flask(__name__)


if 'SENTRY_DSN' in os.environ:
    Sentry(app)  # grabs config from env automatically


db_uri = os.environ.get('DB_URI', DEFAULT_DB_URI)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri


github_keys = [
    'GITHUB_CLIENT_ID',
    'GITHUB_CLIENT_SECRET',
    'GITHUB_CALLBACK_URL',
    'GITHUB_TOKEN',
]
for key in github_keys:
    app.config[key] = os.environ[key]

app.secret_key = os.environ['SECRET_KEY']


db = SQLAlchemy(app)
admin = Admin(app)

import cinch.views
import cinch.auth.views
import cinch.github
