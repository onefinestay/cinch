from flask import g, render_template, url_for
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
    ready_pull_requests = []
    for pull in pulls:
        pull.checks = list(run_checks(pull))
        pull.sync_label = sync_label(pull.ahead_of_master, pull.behind_master)
        pull.url = url_for(
            'pull_request',
            project_owner=pull.project.owner,
            project_name=pull.project.name,
            number=pull.number,
        )
        if (
            all(check.status for check in pull.checks)
            and pull.behind_master == 0
        ):
            ready_pull_requests.append(pull)

    return render_template(
        'index.html',
        pull_requests=pulls,
        ready_pull_requests=ready_pull_requests,
        projects=projects,
    )


@app.route('/pull_request/<project_owner>/<project_name>/<number>')
@requires_auth
def pull_request(project_owner, project_name, number):
    session = db.session

    pull_request = session.query(PullRequest).join(Project).filter(
        PullRequest.number == number,
        Project.owner == project_owner, Project.name == project_name
    ).first()

    if pull_request is None:
        return "Unknown pull request", 404

    pull_request.checks = list(run_checks(pull_request))
    pull_request.sync_label = sync_label(
        pull_request.ahead_of_master, pull_request.behind_master)

    return render_template(
        'pull_request.html', pull=pull_request)


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
        None: 'warning',
        False: 'danger',
    }
    return status_map.get(value, '')
