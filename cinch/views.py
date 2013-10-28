from flask import g, request, render_template
import logging

from cinch import app, db
from cinch.auth.decorators import requires_auth
from cinch.controllers import get_pull_request_status
from cinch.check import run_checks
from cinch.jenkins import handle_data
from cinch.models import PullRequest, Project
from cinch.admin import AdminView

logger = logging.getLogger(__name__)


AdminView  # pyflakes. just want the module imported


def status_label(status):
    if status:
        return "success"
    else:
        return "warning"

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
    pulls = dbsession.query(PullRequest).all()
    projects = dbsession.query(Project).all()
    for pull in pulls:
        unit_status = get_pull_request_status(pull, "unit")
        integration_status = get_pull_request_status(pull, "integration")
        checks = []
        for status, message in run_checks(pull):
            checks.append({
                'name': message,
                'short_name': 'Check',
                'status': status_label(status)
            })
        pull.checks = checks
        pull.sync_label = sync_label(pull.ahead_of_master, pull.behind_master)

    return render_template(
        'index.html', pull_requests=pulls, projects=projects)


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token


@app.route('/api/jenkins/pull', methods=['POST'])
def accept_jenksins_update():
    """ View for jenkins web hooks to handle updates
    """
    logger.debug('receiving jenkins notification')

    data = request.get_data()
    try:
        handle_data(data)
    except Exception, e:
        logger.error(str(e), exc_info=True)
        raise

    return 'OK', 200
