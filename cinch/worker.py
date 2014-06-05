"""Nameko worker for async handling of updates"""

import eventlet
eventlet.monkey_patch()

import logging

from nameko.containers import MAX_WORKERS_CONFIG_KEY
from nameko.events import event_handler, Event
from nameko.messaging import AMQP_URI_CONFIG_KEY
from nameko.runners import ServiceRunner

from cinch import app, db
from cinch.git import Repo
from cinch.models import Project, PullRequest


_logger = logging.getLogger(__name__)


class MasterMoved(Event):
    type = 'master_moved'


class PullRequestMoved(Event):
    type = 'pull_request_moved'


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

    pr.behind_master = behind
    pr.ahead_of_master = ahead
    pr.is_mergeable = is_mergeable


class RepoWorker(object):
    name = 'cinch'

    @event_handler('cinch', MasterMoved)
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

    @event_handler('cinch', PullRequestMoved)
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
        set_relative_states(pull_request)


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

def run_worker():
    config = get_nameko_config()

    service_runner = ServiceRunner(config)
    service_runner.add_service(RepoWorker)

    service_runner.start()
    service_runner.wait()


if __name__ == '__main__':
    run_worker()
