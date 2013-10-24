from flask import session, url_for, redirect, g
from flask.ext.github import GitHub

from cinch import app

github = GitHub(app)

@app.before_request
def before_request():
    if 'access_token' in session:
        g.access_token = session['access_token']
    else:
        g.access_token = None


@github.access_token_getter
def token_getter():
    return g.access_token


@app.route('/good-to-go')
def authenticated():
    return 'authenticated CI is a cinch too!'


@app.route('/failed')
def failed():
    return 'failed to authenticate'


@app.route('/unauthenticated')
def unauthenticated():
    return 'get out of our office'


@app.route('/login/')
def login():
    return github.authorize()


@app.route('/logout/')
def logout():
    session.pop('access_token', None)
    return redirect(url_for('index'))


@app.route('/user')
def user():
	if g.access_token:
		return 'hello %s' % g.access_token
	return 'you are nothing!'


@app.route('/callback/')
@github.authorized_handler
def authorized(access_token):
    if access_token is None:
        return redirect(url_for('failed'))

    session['access_token'] = access_token
    return redirect(url_for('authenticated'))
