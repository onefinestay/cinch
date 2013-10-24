import logging
from flask import request
from github import Github, UnknownObjectException

from cinch import app

logger = logging.getLogger(__name__)

GITHUB_TOKEN = "***REMOVED***"

PROJECT_ORGANIZATION = '***REMOVED***'  # needs to be project configuration

PROJECT_CONFIG = {  # the fully qualified repo name `organization/repo`
    '***REMOVED***': '***REMOVED***/***REMOVED***',
    '***REMOVED***': '***REMOVED***/***REMOVED***',
    '***REMOVED***': '***REMOVED***/***REMOVED***-admin-screens',
}


class GithubAdapter(object):
    """ Constructed with an authenticated :mod:`github.Github` instance.
    """

    def __init__(self, gh):
        self.gh = gh

    def get_repo(self, project):
        repo_name = PROJECT_CONFIG.get(project)

        try:
            repo = self.gh.get_repo(repo_name)
        except UnknownObjectException:
            repo = None

        return repo

    def handle_update(self, data):
        try:
            owner_name = data['owner']['name']
            repo_name = data['repository']['name']
        except KeyError:
            logger.error('Unable to parse data. Malformed request: {}'.format(data))
        repo = self.get_repo('{}/{}'.format(owner_name, repo_name))

        if repo is None:
            logger.warning('received webhook for unconfigured project: {}'.format(repo_name))
            return

        # Do some processing


@app.route('/api/github/pull', methods=['POST'])
def accept_github_update():
    # TODO: if user is logged in, use their token instead of the default one
    token = GITHUB_TOKEN

    gh = Github(token)
    adapter = GithubAdapter(gh)

    data = request.form['payload']

    adapter.handle_update(data)

    return 'OK'
