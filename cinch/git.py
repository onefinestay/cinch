"""Make bare clones of repos to use for faster (local) comparison operations"""

import errno
import logging
import os
import subprocess

from cinch import app


GIT_ERROR = 128
GITHUB_URL_TEMPLATE = "git@github.com:{}/{}.git"

ORIGIN_REMOTE = '+refs/heads/*:refs/remotes/origin/*'
# github exposes pull request heads and merge heads at these endpoints
PULL_REQUEST_REMOTE_TEMPLATE = '+refs/pull/*/head:refs/remotes/{}/*'

_log = logging.getLogger(__name__)


class NotARepo(Exception):
    pass


def add_custom_remote(repo, name, url, spec):
    repo.cmd([
        'remote',
        'add',
        name,
        url,
    ])
    repo.cmd([
        'config',
        'remote.{}.fetch'.format(name),
        spec,
    ])


class Repo(object):
    def __init__(self, path):
        self.path = path

    @classmethod
    def setup_repo(cls, owner, name):
        repo_base_dir = app.config.get('REPO_BASE_DIR')
        owner_base_dir = os.path.join(repo_base_dir, owner)

        try:
            os.makedirs(owner_base_dir)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

        url = GITHUB_URL_TEMPLATE.format(owner, name)

        subprocess.check_call(
            [
                'git',
                'clone',
                '--bare',
                url,
                name,
            ],
            cwd=owner_base_dir,
        )
        repo = cls.from_local_repo(owner, name)

        # bare clones don't get origin by default
        add_custom_remote(
            repo,
            'origin',
            url,
            ORIGIN_REMOTE,
        )
        # add remotes for github pull requests heads and merge heads
        for remote_name in ['pr_head', 'pr_merge']:
            spec = PULL_REQUEST_REMOTE_TEMPLATE.format(remote_name)
            add_custom_remote(
                repo,
                remote_name,
                url,
                spec
            )
        repo.fetch()
        return repo

    @classmethod
    def from_local_repo(cls, owner, name):
        repo_base_dir = app.config.get('REPO_BASE_DIR')
        repo_dir = '{}/{}/{}'.format(repo_base_dir, owner, name)

        repo = cls(repo_dir)
        return repo

    def is_repo(self):
        try:
            self.cmd(['rev-parse'], bubble_errors=True)
        except subprocess.CalledProcessError as ex:
            if ex.returncode == GIT_ERROR:
                return False
            raise
        else:
            return True

    def fetch(self):
        self.cmd(['fetch', '--all'])

    def cmd(self, cmd, bubble_errors=False):
        git_dir = '--git-dir={}'.format(self.path)
        git_cmd = ['git', git_dir] + cmd
        try:
            output = subprocess.check_output(git_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            if bubble_errors:
                raise
            else:
                _log.debug(ex.output)
                return None
        return output.strip()

    def compare(self, base, branch):
        """Count number of commits in branch that are not in base"""
        branches =  '{}..{}'
        branch_arg = branches.format(base, branch)
        cmd = ['rev-list',  '--count', branch_arg]
        output = self.cmd(cmd)
        if output is None:
            return None
        return int(output)

    def compare_pr(self, pr):
        """Return tuple (behind, ahead) comparing pull request to master"""

        branch = 'pr_head/{}'.format(pr)
        base = 'origin/master'

        behind = self.compare(branch, base)
        ahead = self.compare(base, branch)

        return (behind, ahead)

    def is_mergeable(self, pr):
        """Return True if the pull request can merge cleanly into master"""

        branch = 'pr_head/{}'.format(pr)
        base = 'origin/master'

        merge_base = self.cmd(['merge-base', branch, base])
        merge_result = self.cmd(['merge-tree', merge_base, branch, base])
        conflict_marker = '+>>>>>>>'  # '+' first, since this is a diff
        for line in merge_result.splitlines():
            if line.startswith(conflict_marker):
                return False
        return True
