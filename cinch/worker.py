"""Nameko worker for async handling of updates"""

import eventlet
eventlet.monkey_patch()

import logging

from nameko.events import event_handler
from nameko.runners import ServiceRunner

from cinch import db
from cinch.events import MasterMoved, PullRequestMoved, get_nameko_config
from cinch.git import Repo
from cinch.models import Project, PullRequest


_logger = logging.getLogger(__name__)


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
        set_relative_states(pull_request)


def run_worker():
    config = get_nameko_config()

    service_runner = ServiceRunner(config)
    service_runner.add_service(RepoWorker)

    service_runner.start()
    service_runner.wait()


if __name__ == '__main__':
    run_worker()
