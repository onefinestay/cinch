from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy


app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/cinch'


db = SQLAlchemy(app)

import cinch.views
