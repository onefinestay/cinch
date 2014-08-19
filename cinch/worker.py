"""Nameko worker for async handling of updates"""

from contextlib import contextmanager
from functools import wraps
import logging

from flask import url_for
from flask.ext.github import GitHub
from nameko.containers import MAX_WORKERS_CONFIG_KEY
from nameko.events import Event, event_handler
from nameko.messaging import AMQP_URI_CONFIG_KEY
from nameko.standalone.events import event_dispatcher

from cinch import db
from cinch.check import run_checks
from cinch.git import Repo
from cinch.models import Project, PullRequest


_logger = logging.getLogger(__name__)


from cinch import app

github = GitHub(app)


class GithubStatus(object):
    PENDING = 'pending'
    SUCCESS = 'success'
    ERROR = 'error'
    FAILURE = 'failure'

    descriptions = {
        PENDING: 'Rolling, rolling, rolling',
        SUCCESS: 'Great success, ready for release',
        ERROR: 'Something went terribly wrong',
        FAILURE: 'Better luck next time'
    }


class MasterMoved(Event):
    """ The master branch for this project has moved. Reset e.g. merge head,
    mergeable and ahead/behind status for all pull requests for this project.

    :Event data:
        owner : str
            Project owner
        name : str
            Project name
    """

    type = 'master_moved'


class PullRequestMoved(Event):
    """ This pull request has moved. Reset e.g. merge head, mergeable and
    ahead/behind status.

    :Event data:
        owner : str
            Project owner
        name : str
            Project name
        number : int
            Pull request number
    """

    type = 'pull_request_moved'


class PullRequestStatusUpdated(Event):
    """ The build status for this pull request has changed.

    :Event data:
        pull_request : (int, int)
            The pull request number and project id for looking up this pull
            request
    """

    type = 'pull_request_status_updated'


def get_nameko_config():
    amqp_uri = app.config.get('NAMEKO_AMQP_URI')

    if not amqp_uri:
        raise RuntimeError(
            'NAMEKO_AMQP_URI must be configured in order to run this worker'
        )

    return {
        AMQP_URI_CONFIG_KEY: amqp_uri,

        # we're not threadsafe, but don't need concurrency, only async
        MAX_WORKERS_CONFIG_KEY: 1,
    }


@contextmanager
def dispatcher():
    config = get_nameko_config()
    with event_dispatcher('cinch', config) as dispatch:
        yield dispatch


def worker_app_context(func):
    """ Allows offline generation of urls using `url_for` if a `SERVER_NAME`
    was provided as part of the application configuration.
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        with app.app_context():
            return func(*args, **kwargs)

    return wrapped


def set_relative_states(pr, fetch=True):
    """Set values of states that are relative to the base branch"""

    project = pr.project
    git_repo = Repo.from_local_repo(project.owner, project.name)
    if not git_repo.is_repo():
        git_repo = Repo.setup_repo(project.owner, project.name)

    if fetch:
        git_repo.fetch()

    # we currently assume that the base is master
    behind, ahead = git_repo.compare_pr(pr.number)
    is_mergeable = git_repo.is_mergeable(pr.number)
    merge_head = git_repo.merge_head(pr.number)

    pr.behind_master = behind
    pr.ahead_of_master = ahead
    pr.is_mergeable = is_mergeable
    pr.merge_head = merge_head


def determine_pull_request_status(pull_request):
    # only iterate over the generator once
    checks = [check for check in run_checks(pull_request)]

    if all(check.status for check in checks):
        return GithubStatus.SUCCESS
    # TODO: fail fast or wait till build is complete before recording failure
    elif any(check.status is False for check in checks):
        return GithubStatus.FAILURE
    elif any(check.status is None for check in checks):
        return GithubStatus.PENDING


class RepoWorker(object):
    name = 'cinch'

    @event_handler('cinch', MasterMoved, reliable_delivery=True)
    def master_moved(self, event_data):
        project_owner = event_data['owner']
        project_name = event_data['name']

        first = True
        pull_requests = db.session.query(
            PullRequest).join(Project).filter(
                Project.owner == project_owner,
                Project.name == project_name,
                PullRequest.is_open,
            )

        for pull_request in pull_requests:
            set_relative_states(pull_request, fetch=first)
            first = False

        db.session.commit()

    @event_handler('cinch', PullRequestMoved, reliable_delivery=True)
    def pull_request_moved(self, event_data):
        project_owner = event_data['owner']
        project_name = event_data['name']
        number = event_data['number']

        pull_request = db.session.query(
            PullRequest).join(Project).filter(
                Project.owner == project_owner,
                Project.name == project_name,
                PullRequest.number == number,
            ).one()
        set_relative_states(pull_request, fetch=True)

        db.session.commit()

    @event_handler('cinch', PullRequestStatusUpdated, reliable_delivery=True)
    @worker_app_context
    def pull_request_status_updated(self, event_data):
        pull_request = db.session.query(PullRequest).get(
            event_data['pull_request'])
        project = pull_request.project

        if not project.update_status:
            return

        status = determine_pull_request_status(pull_request)
        detail_url = url_for(
            'jenkins.pull_request_status',
            project_owner=project.owner,
            project_name=project.name,
            pr_number=pull_request.number,
        )

        payload = {
            "state": status,
            "target_url": detail_url,
            "description": GithubStatus.descriptions.get(status, ''),
            "context": "continuous-integration/cinch"
        }

        status_uri = 'repos/{owner}/{project}/statuses/{sha}'.format(
            owner=project.owner,
            project=project.name,
            sha=pull_request.head,
        )
        github.post(status_uri, payload)
