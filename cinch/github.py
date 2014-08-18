from __future__ import absolute_import

from collections import namedtuple
import logging
from flask import request
from nameko.standalone.events import event_dispatcher
from sqlalchemy.orm.exc import NoResultFound

from cinch import app, db
from cinch.models import Project, PullRequest
from cinch.check import check, CheckStatus
from cinch.worker import MasterMoved, PullRequestMoved, get_nameko_config

logger = logging.getLogger(__name__)

MASTER_REF = 'refs/heads/master'
PULL_REQUEST_OPEN_STATE = 'open'

RepoInfo = namedtuple('RepoInfo', ['owner', 'name'])
PullRequestInfo = namedtuple(
    'PullRequestInfo',
    ['number', 'title', 'head', 'user', 'state', 'base_ref'])


class HookEvents(object):
    """Constants for the X-Github-Event header used to signal event type"""
    HEADER_KEY = 'X-GitHub-Event'

    PING = 'ping'
    PUSH = 'push'
    PULL_REQUEST = 'pull_request'


class Responses(object):
    UNKNOWN_PROJECT = "Ignoring: Unknown project"
    UNKNOWN_ACTION = "Ignoring: Unknown action"
    NON_MASTER_PUSH = "Ignoring: Non-master push"
    NON_MASTER_PR = "Ignoring: Not against master"

    MASTER_PUSH_OK = "Master push handled"
    PR_OK = "Pull request updated"


class GithubHookParser(object):
    """Parses data from a Flask request object from a github webhook
    """
    MASTER = 'master'
    MASTER_REF = 'refs/heads/master'

    def __init__(self, request):
        self.event_type = request.headers[HookEvents.HEADER_KEY]

        if self.is_ping():
            self.data = None
            return

        self.data = request.json

    def get_repo_info(self):
        """Return RepoInfo namedtuple (owner, name)"""
        repo_info = self.data['repository']

        repo_name = repo_info['name']
        owner_info = repo_info['owner']
        # payloads for different events have different representations (sigh)
        owner_name = owner_info.get('name') or owner_info.get('login')

        return RepoInfo(owner_name, repo_name)

    def get_pull_request_info(self):
        """Returns the pull request number, or None if this is not a
        pull request event
        """
        if self.event_type != HookEvents.PULL_REQUEST:
            return None

        pr_info = self.data['pull_request']

        pr_number = pr_info['number']
        title = pr_info['title']
        head = pr_info['head']['sha']
        state = pr_info['state']
        base_ref = pr_info['base']['ref']
        user = pr_info['user']['login']

        return PullRequestInfo(
            number=pr_number,
            title=title,
            head=head,
            user=user,
            state=state,
            base_ref=base_ref,
        )

    def is_ping(self):
        return self.event_type == HookEvents.PING

    def is_pull_request(self):
        return self.event_type == HookEvents.PULL_REQUEST

    def is_push(self):
        return self.event_type == HookEvents.PUSH

    def is_master_push(self):
        return (
            self.event_type == HookEvents.PUSH and
            self.data['ref'] == self.MASTER_REF
        )


def get_project_from_repo_info(repo_info):
    try:
        return Project.query.filter_by(
            owner=repo_info.owner,
            name=repo_info.name,
        ).one()
    except NoResultFound:
        return None


@app.route('/api/github/update', methods=['POST'])
def handle_github_webhok():
    """We always return a 200 to keep github happy, but include info about
    actions taken
    """
    # TODO: verify request is from github

    parser = GithubHookParser(request)

    if parser.is_ping():
        return "pong"

    if parser.is_push():
        if not parser.is_master_push():
            return Responses.NON_MASTER_PUSH
        return handle_push(parser)

    elif parser.is_pull_request():
        return handle_pull_request(parser)

    else:
        return Responses.UNKNOWN_ACTION


def handle_push(parser):
    repo_info = parser.get_repo_info()
    project = get_project_from_repo_info(repo_info)
    if project is None:
        return Responses.UNKNOWN_PROJECT

    pull_requests = db.session.query(
        PullRequest).filter(
            PullRequest.project == project,
            PullRequest.is_open,
        )

    for pr in pull_requests:
        pr.behind_master = None
        pr.ahead_of_master = None
        pr.is_mergeable = None
        pr.merge_head = None

    db.session.commit()

    config = get_nameko_config()
    with event_dispatcher('cinch', config) as dispatch:
        event = MasterMoved(data={
            'owner': project.owner,
            'name': project.name,
        })
        dispatch(event)

    return Responses.MASTER_PUSH_OK


def handle_pull_request(parser):
    # TODO: handle pull requests across different repos (forks)
    # we currently assume same repo. See #24
    repo_info = parser.get_repo_info()
    project = get_project_from_repo_info(repo_info)
    if project is None:
        return Responses.UNKNOWN_PROJECT

    pr_info = parser.get_pull_request_info()
    if pr_info.base_ref != GithubHookParser.MASTER:
        # TODO: track these with a separate check "is_against_master"?
        # if so, set_relative_states needs to get the base sha or similar,
        # to pass to the git repo.
        return Responses.NON_MASTER_PR

    pr = PullRequest.query.get((pr_info.number, project.id))
    if pr is None:
        # we need to initialise the pull request as it's the
        # first time we've heard of it
        pr = PullRequest(
            number=pr_info.number,
            project=project,
            owner=pr_info.user,
        )
        db.session.add(pr)

    pr.title = pr_info.title
    pr.is_open = (pr_info.state == PULL_REQUEST_OPEN_STATE)
    pr.head = pr_info.head
    pr.merge_head = None
    db.session.commit()

    config = get_nameko_config()
    with event_dispatcher('cinch', config) as dispatch:
        event = PullRequestMoved(data={
            'owner': project.owner,
            'name': project.name,
            'number': pr.number,
        })
        dispatch(event)
    return Responses.PR_OK


# Checks

@check
def check_strictly_ahead(pull):
    if pull.ahead_of_master > 0 and pull.behind_master == 0:
        # pull request is ahead of master and up to date with the latest head
        return CheckStatus(label='Branch is up to date', status=True)
    elif pull.ahead_of_master > 0 and pull.behind_master > 0:
        # pull request is ahead of master and up to date with the latest head
        return CheckStatus(
            label='Branch is not up to date with master',
            status=None,
        )
    else:
        return CheckStatus(
            label='Branch has been already merged',
            status=None,
        )


@check
def check_mergeable(pull):
    status = pull.is_mergeable
    labels = {
        True: 'Mergeable',
        False: 'Not automatically mergeable',
        None: 'Merge status unknown',
    }

    label = labels[status]
    return CheckStatus(label=label, status=status)
