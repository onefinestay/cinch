"""Make bare clones of repos to use for faster (local) comparison operations"""

# import re
import subprocess
import logging

from flask import app


GIT_ERROR = 128
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
    def setup_repo(cls, name, url, repo_base_dir=None):
        if repo_base_dir is None:
            repo_base_dir = app.config.get('REPO_BASE_DIR')
        subprocess.check_output(
            [
                'git',
                'clone',
                '--bare',
                url,
                name,
            ],
            cwd=repo_base_dir,
        )
        repo_dir = '{}/{}'.format(repo_base_dir, name)
        repo = cls(repo_dir)

        for remote_name in ['pr_head', 'pr_merge']:
            spec = '+refs/pull/*/head:refs/remotes/{}/*'.format(remote_name)
            add_custom_remote(
                repo,
                remote_name,
                url,
                spec
            )
        repo.fetch()
        return repo

    def fetch(self):
        try:
            self.cmd(['fetch', '--all'])
        except subprocess.CalledProcessError as ex:
            if ex.returncode == GIT_ERROR:
                raise NotARepo()
            raise

    def cmd(self, cmd):
        git_dir = '--git-dir={}'.format(self.path)
        git_cmd = ['git', git_dir] + cmd
        try:
            output = subprocess.check_output(git_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            _log.debug(ex.output)
            return None
        return output

    def compare(self, base, branch):
        """Count number of commits in branch that are not in base"""
        branches =  '{}..{}'
        branch_arg = branches.format(base, branch)
        cmd = ['rev-list',  '--count', branch_arg]
        output = self.cmd(cmd)
        if output is None:
            return None
        return int(output.strip())

    def compare_pr(self, pr):
        """Return tuple (behind, ahead) comparing pull request to master"""

        branch = 'pr_head/{}'.format(pr)
        base = 'master'

        behind = self.compare(branch, base)
        ahead = self.compare(base, branch)

        return (behind, ahead)
