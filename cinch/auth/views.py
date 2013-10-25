from flask import session, url_for, redirect, render_template
from flask.ext.github import GitHub

from cinch import app

github = GitHub(app)


@github.access_token_getter
def token_getter():
    return session.get('access_token')


@app.route('/failed')
def failed():
    return render_template('authentication_failed.html')


@app.route('/unauthenticated')
def unauthenticated():
    return redirect(url_for('login'))


@app.route('/login/')
def login():
    return github.authorize()


@app.route('/logout/')
def logout():
    session.clear()
    return render_template('logged_out.html')


@app.route('/user')
def user():
    if session.get('access_token'):
        return 'hello %s' % session['gh-username']
    return 'you are nothing!'


@app.route('/callback/')
@github.authorized_handler
def authorized(access_token):
    if access_token is None:
        return redirect(url_for('failed'))

    session['access_token'] = access_token
    user_dict = github.get('user')
    session['gh-username'] = user_dict["login"]
    session['gh-gravatar'] = user_dict["avatar_url"]

    return redirect(url_for('index'))
