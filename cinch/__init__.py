import os

from flask import Flask
from flask.ext.admin import Admin
from flask.ext.sqlalchemy import SQLAlchemy
from raven.contrib.flask import Sentry


DEFAULT_DB_URI = 'sqlite://'


app = Flask(__name__)


for key, value in os.environ.items():
    if not key.startswith('CINCH_'):
        continue

    config_key = key.replace('CINCH_', '', 1)
    app.config[config_key] = value

app.secret_key = app.config['SECRET_KEY']


if 'SENTRY_DSN' in app.config:
    Sentry(app, dsn=app.config['SENTRY_DSN'])

db_uri = app.config.get('DB_URI', DEFAULT_DB_URI)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri


db = SQLAlchemy(app)
admin = Admin(app)

import cinch.views
import cinch.auth.views
import cinch.github

cinch  # pyflakes
