from flask import g, render_template
import logging

from cinch import app, db
from cinch.auth.decorators import requires_auth
from cinch.check import run_checks
from cinch.models import PullRequest, Project
from cinch.admin import AdminView
from cinch.jenkins.views import jenkins

logger = logging.getLogger(__name__)


AdminView  # pyflakes. just want the module imported


app.register_blueprint(jenkins, url_prefix='/jenkins')


def sync_label(ahead, behind):
    """ Changes the color of the label in behind and ahead of master
    The thinking is:
        * ahead and behind == error
        * ahead not behind == success
        * not ahead but behind == shouldn't show
        * not ahead and not behind == shouldn't show
    """
    if ahead == 0:
        return "warning"
    if behind > 0:
        return "warning"
    else:
        return "success"


@app.route('/')
@requires_auth
def index():
    dbsession = db.session
    pulls = dbsession.query(PullRequest).filter(
        PullRequest.is_open == True).all()
    projects = dbsession.query(Project).all()
    for pull in pulls:
        pull.checks = list(run_checks(pull))
        pull.sync_label = sync_label(pull.ahead_of_master, pull.behind_master)

    return render_template(
        'index.html', pull_requests=pulls, projects=projects)


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token


# TODO: move
@app.template_filter('status_label')
def status_label_filter(value):
    status_map = {
        True: 'success',
        False: 'warning',
    }
    return status_map.get(value, '')
