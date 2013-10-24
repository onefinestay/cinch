import logging
from flask import request
from github import Github, UnknownObjectException

from cinch import app
from cinch.check import check, get_checks

logger = logging.getLogger(__name__)

MASTER_REF = 'refs/heads/master'

GITHUB_TOKEN = "***REMOVED***"

PROJECT_ORGANIZATION = '***REMOVED***'  # needs to be project configuration

PROJECT_CONFIG = {  # the fully qualified repo name `organization/repo`
    '***REMOVED***': '***REMOVED***/***REMOVED***',
    '***REMOVED***': '***REMOVED***/***REMOVED***',
    '***REMOVED***': '***REMOVED***/***REMOVED***-admin-screens',
}


class GithubUpdateHandler(object):
    """ Constructed with an authenticated :mod:`github.Github` instance and a
        `data` dictionary describing the update.
    """

    def __call__(self, gh, data):
        self.gh = gh
        self.data = data

        if self.repo is None:
            logger.warning(
                'received webhook for unconfigured project:\n'
                '{}'.format(data))
            return

        # TODO: determine whether this update was triggered by a pull
        #       request or master (aka. if we're interested)
        pull_request_data = data.get('pull_request')
        if pull_request_data is None and data['ref'] != MASTER_REF:
            # we don't care about this update
            return

        # Perform checks
        for check_method in get_checks(self):
            check_method()

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
    def up_to_date(self):
        # Find out the current master SHA. Consider using local git to find
        # this to avoid the api call
        master_sha = self.repo.get_branch('master').commit.sha

        head_sha = self.data.get('after')

        try:
            status = self.repo.compare(master_sha, head_sha)
        except (UnknownObjectException, AssertionError):
            logger.warning(
                'unable to perform up_to_date check between commits: '
                '{}, {}'.format(master_sha, head_sha))
            return

        if status.behind_by > 0:
            # set flag to false
            pass
        elif status.ahead_by <= 0:
            # pull request has been merged
            pass
        else:
            # Pull Request is ahead of master and up to date.
            # It's still active
            pass

handle_github_update = GithubUpdateHandler()


@app.route('/api/github/pull', methods=['POST'])
def accept_github_update():
    """ View for github web hooks to handle updates
    """
    # TODO: if user is logged in, use their token instead of the default one
    token = GITHUB_TOKEN

    gh = Github(token)
    data = request.form['payload']

    handle_github_update(gh, data)

    return 'OK'
