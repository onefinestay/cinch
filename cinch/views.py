from flask import g

from cinch import app
from cinch.auth import requires_auth


@app.route('/')
def index():
    message = """
        <p>Hello World!<br>CI is a cinch!<br>
             <a href="/login/">login</a></br>
             <a href="/logout/">logout</a></br>
             <a href="/user">you</a></br>
             <a href="/secret/">secret</a>
        </p>"""

    return message


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token
