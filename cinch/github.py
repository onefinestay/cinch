from __future__ import absolute_import

import json
import logging
from flask import request
from github import Github, UnknownObjectException

from cinch import app, db
from cinch.check import check, get_checks

logger = logging.getLogger(__name__)

MASTER_REF = 'refs/heads/master'

GITHUB_TOKEN = "***REMOVED***"

REPO_TO_PROJECT_MAP = {
    '***REMOVED***': '***REMOVED***',
    '***REMOVED***-admin-screens': '***REMOVED***',
}


class GithubUpdateHandler(object):
    """ Constructed with an authenticated :mod:`github.Github` instance and a
        `data` dictionary describing the update.
    """

    def _handle_pull_request(self, pull_request_data):
        """ handle update to pull request... perform checks
        """

        pr_number = pull_request_data['number']
        # need to get project_id
        project_name = REPO_TO_PROJECT_MAP[self.repo.name]
        project = db.Project.filter.filter_by(name=project_name).one()
        pull = db.PullRequest.query.get(pr_number, project.id)

        if pull is None:
            # we need to initialise the pull request as it's the
            # first time we've heard of it
            pull = db.PullRequest(
                number=pr_number,
                project_id=project.id,
            )
            db.session.add(pull)

        for check_method in get_checks(self):
            check_method(pull, pull_request_data)

    def _handle_master_update(self):
        # get all pulls related to that project and invalidate them
        for gh_pull in self.repo.get_pulls():
            self._handle_pull_request(gh_pull._rawData)

    def __call__(self, gh, data):
        self.gh = gh
        self.data = data

        if (
            self.repo is None or
            self.repo.name not in REPO_TO_PROJECT_MAP.keys()
        ):
            logger.warning(
                'received webhook for unconfigured project:\n'
                '{}'.format(data))
            return

        pull_request_data = data.get('pull_request')
        if pull_request_data is not None:
            self._handle_pull_request(pull_request_data)

        if data['ref'] == MASTER_REF:
            self._handle_master_update()

        db.session.commit()

    _repo = None

    @property
    def repo(self):
        if self._repo is None:
            try:
                owner_name = self.data['owner']['name']
                repo_name = self.data['repository']['name']
            except KeyError:
                logger.error(
                    'Unable to parse data. Malformed request:\n'
                    '{}'.format(self.data))
                return

            self.repo_name = '{}/{}'.format(owner_name, repo_name)

            try:
                self._repo = self.gh.get_repo(repo_name)
            except UnknownObjectException:
                self._repo = None

        return self._repo

    @check
    def up_to_date(self, pull, data):
        # Find out the current master SHA. Consider using local git to find
        # this to avoid the api call
        master_sha = self.repo.get_branch('master').commit.sha

        head_sha = data['head']['sha']

        try:
            status = self.repo.compare(master_sha, head_sha)
        except (UnknownObjectException, AssertionError):
            logger.warning(
                'unable to perform up_to_date check between commits: '
                '{}, {}'.format(master_sha, head_sha))
            return

        if pull:
            pull.behind_master = status.behind_by
            pull.ahead_of_master = status.ahead_by

    @check
    def is_mergeable(self, pull, data):
        """ TODO!
        """
        # pretty sure data['mergeable'] is null at the point of the
        # hook being sent

    @check
    def current_head_commit(self, pull, data):
        pull.head_commit = data['head']['sha']


handle_github_update = GithubUpdateHandler()


@app.route('/api/github/update', methods=['POST'])
def accept_github_update():
    """ View for github web hooks to handle updates
    """
    # TODO: if user is logged in, use their token instead of the default one
    token = GITHUB_TOKEN

    gh = Github(token)
    data = request.form['payload']
    data = json.loads(data)

    handle_github_update(gh, data)

    return 'OK'
