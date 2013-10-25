from flask import g, render_template

from cinch import app
from cinch.auth import requires_auth


@app.route('/')
@requires_auth
def index():
    return render_template('index.html')


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token
