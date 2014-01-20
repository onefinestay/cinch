from __future__ import absolute_import

import json
import logging
from flask import request
from github import Github, UnknownObjectException

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


class GithubUpdateHandler(object):
    """ Constructed with an authenticated :mod:`github.Github` instance and a
        `data` dictionary describing the update.
    """

    def _handle_pull_request(self, pull_request_data):
        """ handle update to pull request... perform checks
        """

        pr_number = pull_request_data['number']
        project = models.Project.query.filter_by(
            repo_name=self.repo.name).one()

        head_sha = pull_request_data['head']['sha']
        commit = get_or_create_commit(head_sha, project)

        title = pull_request_data.get('title', '')

        pull = models.PullRequest.query.get((pr_number, project.id))
        if pull is None:
            # we need to initialise the pull request as it's the
            # first time we've heard of it
            pull = models.PullRequest(
                number=pr_number,
                project_id=project.id,
                owner=pull_request_data['user']['login'],
                title=title,
            )
            models.db.session.add(pull)

        pull.head_commit = commit.sha



        models.db.session.commit()

    def _handle_master_update(self):
        project = models.Project.query.filter_by(
            repo_name=self.repo.name).one()

        # at this point we are processing an update on the master branch
        # `after` is the head of the branch after this commit
        master_sha = self.data['after']

        commit = get_or_create_commit(master_sha, project)

        project.master_sha = commit.sha

        # get all pulls related to that project and invalidate them
        for gh_pull in self.repo.get_pulls():
            self._handle_pull_request(gh_pull._rawData)

    def __call__(self, gh, data):
        self.gh = gh
        self.data = data

        if (
            self.repo is None or
            models.Project.query.filter_by(
                repo_name=self.repo.name).count() == 0
        ):
            logger.warning(
                'received webhook for unconfigured project:\n'
                '{}'.format(data))
            return

        pull_request_data = data.get('pull_request')
        if pull_request_data is not None:
            self._handle_pull_request(pull_request_data)

        if 'ref' in data and data['ref'] == MASTER_REF:
            # this is an update to the master branch
            self._handle_master_update()

    _repo = None

    @property
    def repo(self):
        if self._repo is None:
            repo_data = self.data['repository']
            try:
                repo_name = repo_data['name']

                owner_data = repo_data['owner']
                owner_name = owner_data.get('name')
                if owner_name is None:
                    owner_name = owner_data.get('login')
                if owner_name is None:
                    raise KeyError("Neither login nor name found for owner")

            except KeyError:
                logger.error(
                    'Unable to parse data. Malformed request:\n'
                    '{}'.format(repo_data))
                return

            repo_id = '{}/{}'.format(owner_name, repo_name)

            try:
                self._repo = self.gh.get_repo(repo_id)
            except UnknownObjectException:
                self._repo = None

        return self._repo

    def update_pull_data(self, pull, data):
        # update row with null values to stop parallel processes from
        # picking up stale state while we look stuff up from github
        pull.behind_master = None
        pull.ahead_of_master = None
        models.db.session.commit()

        # Find out the current master SHA. Consider using local git to find
        # this to avoid the api call
        project = models.Project.query.filter_by(
            repo_name=self.repo.name).one()

        head_sha = data['head']['sha']

        try:
            status = self.repo.compare(project.master_sha, pull.head_commit)
        except (UnknownObjectException, AssertionError):
            logger.warning(
                'unable to update pull request when comparing commits: '
                '{}, {}'.format(project.master_sha, head_sha))
            return

        pull.behind_master = status.behind_by
        pull.ahead_of_master = status.ahead_by

        # TODO: check mergeable status ... may not be possible with data sent
        #       in the github notifcation so call may need to be done
        #       subsequently


handle_github_update = GithubUpdateHandler()


@app.route('/api/github/update', methods=['POST'])
def accept_github_update():
    """ View for github web hooks to handle updates
    """
    # TODO: verify request is from github

    github_token = app.config.get('GITHUB_TOKEN')
    gh = Github(github_token)
    data = request.form['payload']
    data = json.loads(data)

    handle_github_update(gh, data)

    return 'OK'


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
