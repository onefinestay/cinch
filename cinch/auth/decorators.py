from functools import wraps

from flask import session, redirect, url_for


def is_authenticated():
    return session.get('access_token')


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('unauthenticated'))
        return f(*args, **kwargs)
    return decorated
