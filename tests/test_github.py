import json

from mock import patch
import pytest

from cinch import app
from cinch.github import Responses
from cinch.models import Project, PullRequest

URL = '/api/github/update'


@pytest.yield_fixture(autouse=True)
def fake_repo():
    with patch('cinch.github.Repo', autospec=True) as Repo:
        Repo.from_local_repo('owner', 'name').compare_pr.return_value = (
            None, None)
        yield Repo


@pytest.fixture(autouse=True)
def propagate_exceptions():
    app.config['PROPAGATE_EXCEPTIONS'] = True


@pytest.fixture
def hook_post():
    client = app.test_client()
    def poster(data, event_type):
        headers = {
            'Content-type': 'application/json',
            'X-GitHub-Event': event_type,
        }
        serialised = json.dumps(data)
        return client.post(URL, data=serialised, headers=headers)
    return poster



def test_ping():
    client = app.test_client()
    res = client.post(URL, headers={'X-GitHub-Event': 'ping'})
    assert res.data == 'pong'


def test_unknown_project(hook_post):
    data = {
        'repository': {
            'name': 'unknown',
            'owner': {
                'name': 'unknown',
            },
        },
        'ref': "refs/heads/master",
    }
    res = hook_post(data, 'push')
    assert res.status_code == 200
    assert res.data == Responses.UNKNOWN_PROJECT


def test_unknown_action(hook_post):
    data = {
        'repository': {
            'name': 'unknown',
            'owner': {
                'name': 'unknown',
            },
        },
    }
    res = hook_post(data, 'unknown')
    assert res.status_code == 200
    assert res.data == Responses.UNKNOWN_ACTION


class TestPush(object):
    @pytest.fixture(autouse=True)
    def project(self, session):
        project = Project(owner='my_owner', name='my_name')
        session.add(project)
        session.commit()
        return project

    def test_non_master(self, hook_post):
        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/my_branch",
        }
        res = hook_post(data, 'push')
        assert res.status_code == 200
        assert res.data == Responses.NON_MASTER_PUSH

    def test_master(self, hook_post):
        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/master",
        }
        res = hook_post(data, 'push')
        assert res.status_code == 200
        assert res.data == Responses.MASTER_PUSH_OK

    def test_unseen_repo(self, fake_repo, session, project, hook_post):
        pr1 = PullRequest(
            project=project, head='sha1', owner='me', title='foo', is_open=True)
        session.add(pr1)
        session.commit()

        is_repo = fake_repo.from_local_repo('mock_owner', 'mock_name').is_repo
        is_repo.return_value = False

        setup_repo = fake_repo.setup_repo
        repo = setup_repo('mock_owner', 'mock_name')
        repo.compare_pr.return_value = (
            None, None)
        repo.is_mergeable.return_value = False

        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/master",
        }
        hook_post(data, 'push')
        assert setup_repo.call_count == 2  # once to set up mock, once in code
        args1, _ = setup_repo.call_args_list[0]
        args2, _ = setup_repo.call_args_list[1]
        assert args1 == ('mock_owner', 'mock_name')
        assert args2 == ('my_owner', 'my_name')


    def test_master_with_open_prs(self, session, project, fake_repo, hook_post):
        pr1 = PullRequest(
            project=project, head='sha1', owner='me', title='foo', is_open=True)
        pr2 = PullRequest(
            project=project, head='sha2', owner='me', title='foo', is_open=True)
        pr3 = PullRequest(
            project=project, head='sha2', owner='me', title='foo', is_open=False)
        session.add(pr1)
        session.add(pr2)
        session.add(pr3)
        session.commit()

        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/master",
        }

        repo = fake_repo.from_local_repo('owner', 'name')
        repo.is_mergeable.return_value = False

        res = hook_post(data, 'push')
        assert res.status_code == 200
        assert res.data == Responses.MASTER_PUSH_OK

        assert repo.compare_pr.call_count == 2
        args1, _ = repo.compare_pr.call_args_list[0]
        args2, _ = repo.compare_pr.call_args_list[1]
        assert args1 == (1,)
        assert args2 == (2,)
        assert repo.fetch.call_count == 1  # not once per pr


class TestPullRequest(object):
    @pytest.fixture(autouse=True)
    def project(self, session):
        project = Project(owner='my_owner', name='my_name')
        session.add(project)
        session.commit()
        return project

    def test_new(self, session, hook_post, fake_repo):
        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/master",
            'pull_request': {
                'number': 1,
                'title': 'some title',
                'head': {
                    'sha': '1',
                },
                'state': 'open',
                'base': {
                    'ref': 'master',
                },
            },
        }
        repo = fake_repo.from_local_repo('owner', 'name')
        repo.is_mergeable.return_value = False

        assert session.query(PullRequest).count() == 0

        res = hook_post(data, 'pull_request')
        assert res.status_code == 200
        assert res.data == Responses.PR_OK

        assert session.query(PullRequest).count() == 1

    def test_ignore_not_against_master(self, session, hook_post):
        data = {
            'repository': {
                'name': 'my_name',
                'owner': {
                    'name': 'my_owner',
                },
            },
            'ref': "refs/heads/master",
            'pull_request': {
                'number': 1,
                'title': 'some title',
                'head': {
                    'sha': '1',
                },
                'state': 'open',
                'base': {
                    'ref': 'other',
                },
            },
        }

        assert session.query(PullRequest).count() == 0

        res = hook_post(data, 'pull_request')
        assert res.data == Responses.NON_MASTER_PR

        assert session.query(PullRequest).count() == 0

    def test_unknown_project(self, hook_post, session):
        data = {
            'repository': {
                'name': 'unknown',
                'owner': {
                    'name': 'unknown',
                },
            },
            'ref': "refs/heads/master",
            'pull_request': {
                'number': 1,
                'title': 'some title',
                'head': {
                    'sha': '1',
                },
                'state': 'open',
                'base': {
                    'ref': 'master',
                },
            },
        }

        res = hook_post(data, 'pull_request')
        assert res.data == Responses.UNKNOWN_PROJECT
        assert session.query(PullRequest).count() == 0
