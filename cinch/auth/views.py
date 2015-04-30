from flask import session, url_for, redirect, render_template, request
from flask.ext.github import GitHub

from cinch import app


github = GitHub(app)


@github.access_token_getter
def token_getter():
    return session.get('access_token')


@app.route('/failed')
def failed():
    return render_template('authentication_failed.html')


@app.route('/login')
def login():
    redirect_uri = url_for('authorized', next=request.args.get('next'), _external=True)
    return github.authorize(
        redirect_uri=redirect_uri
    )


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
    next_url = request.args.get('next') or url_for('index')
    if access_token is None:
        return redirect(url_for('failed'))

    session['access_token'] = access_token
    user_dict = github.get('user')
    session['gh-username'] = user_dict["login"]
    session['gh-gravatar'] = user_dict["avatar_url"]

    return redirect(next_url)
