from __future__ import absolute_import

from collections import namedtuple
import json
import logging
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from cinch import app, models
from cinch.check import check, CheckStatus

logger = logging.getLogger(__name__)

MASTER_REF = 'refs/heads/master'


def get_or_create_commit(sha, project):
    commit = models.Commit.query.get(sha)
    if commit is None:
        commit = models.Commit(sha=sha, project=project)
        models.db.session.add(commit)
        models.db.session.flush()

    return commit


RepoInfo = namedtuple('RepoInfo', ['owner', 'name'])
PullRequestInfo = namedtuple(
    'PullRequestInfo', ['number', 'title', 'head', 'state', 'base_ref'])


class GithubHookParser(object):
    """Parses data from a Flask request object from a github webhook
    """
    EVENT_HEADER = 'X-GitHub-Event'
    MASTER = 'master'
    MASTER_REF = 'refs/heads/master'

    class Events(object):
        PING = 'ping'
        PUSH = 'push'
        PULL_REQUEST = 'pull_request'

    def __init__(self, request):
        self.event_type = request.headers[self.EVENT_HEADER]

        if self.is_ping():
            self.data = None
            return

        data = request.form['payload']
        self.data = json.loads(data)

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
        if self.event_type != self.Events.PULL_REQUEST:
            return None

        pr_info = self.data['pull_request']

        pr_number = pr_info['number']
        title = pr_info['title']
        head = pr_info['head']['sha']
        state = pr_info['state']
        base_ref = ['base']['ref']

        return PullRequestInfo(
            number=pr_number,
            title=title,
            head=head,
            state=state,
            base_ref=base_ref,
        )

    def is_ping(self):
        return self.event_type == self.Events.PING

    def is_pull_request(self):
        return self.event_type == self.Events.PULL_REQUEST

    def is_push(self):
        return self.event_type == self.Events.PUSH

    def is_master_push(self):
        return (
            self.event_type == self.Events.PUSH and
            self.data['ref'] == self.MASTER_REF
        )


@app.route('/api/github/update', methods=['POST'])
def handle_github_webhok():
    parser = GithubHookParser(request)

    if parser.is_ping():
        return "pong"

    if parser.is_push() and not parser.is_master_push():
        return "Ignoring: Non-master push"

    if parser.is_pull_request():
        repo_info = parser.get_repo_info()
        pr_info = parser.get_pull_request_info()
        return handle_pull_request(repo_info, pr_info)


def handle_pull_request(repo_info, pr_info):
    # TODO: handle pull requests across different repos (forks)
    # we currently assume same repo

    if pr_info.base_ref != GithubHookParser.MASTER:
        # TODO: track these with a separate check "is_against_master"?
        # if so, set_relative_states needs to get the base sha or similar
        return "Ignoring: Not against master"

    try:
        project = models.Project.query.filter_by(
            repo_name=repo_info.name).one()
    except NoResultFound:
        return "Ignoring: Unknown project"

    # TODO: determine ahead/behind/mergeable (also needed for master push,
    # but for all open prs)

    commit = get_or_create_commit(pr_info.head, project)
    pr = models.PullRequest.query.get((pr_info.number, project.id))
    if pr is None:
        # we need to initialise the pull request as it's the
        # first time we've heard of it
        pr = models.PullRequest(
            number=pr_info.number,
            project_id=project.id,
            owner=repo_info.owner,
            title=pr_info.title,
            is_open=(pr_info.state == 'open'),
        )
        models.db.session.add(pr)

    pr.head_commit = commit.sha
    models.db.session.commit()
    return "Pull request updated"


def set_relative_states(pr):
    """Set values of states that are relative to the base branch"""

    # we currently assume that the base is master


## Checks

@check
def check_strictly_ahead(pull):
    if pull.ahead_of_master > 0 and pull.behind_master == 0:
        # pull request is ahead of master and up to date with the latest head
        return CheckStatus(label='Branch is up to date', status=True)
    elif pull.ahead_of_master > 0 and pull.behind_master > 0:
        # pull request is ahead of master and up to date with the latest head
        return CheckStatus(label='Branch is not up to date with master', status=False)
    else:
        return CheckStatus(label='Branch has been already merged', status=False)


@check
def check_mergeable(pull):
    if pull.is_mergeable:
        return CheckStatus(label='Mergeable', status=True)
    else:
        return CheckStatus(label='Not automatically mergeable', status=False)
