import json

from mock import patch
import pytest

from cinch import app
from cinch.github import Responses
from cinch.models import Project, PullRequest
from cinch.worker import MasterMoved, PullRequestMoved

URL = '/api/github/update'


@pytest.fixture(autouse=True)
def propagate_exceptions():
    app.config['PROPAGATE_EXCEPTIONS'] = True


@pytest.yield_fixture(autouse=True)
def mock_dispatch():
    with patch('cinch.github.event_dispatcher') as dispatcher:
        yield dispatcher().__enter__()


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

    def test_non_master(self, hook_post, mock_dispatch):
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
        assert mock_dispatch.call_count == 0

    def test_master(self, session, project, hook_post, mock_dispatch):
        pr = PullRequest(
            project=project, number=1, head='sha1', owner='me', title='foo',
            ahead_of_master=1, behind_master=2, is_open=True,
        )
        session.add(pr)
        session.commit()
        data = {
            'repository': {
                'name': project.name,
                'owner': {
                    'name': project.owner,
                },
            },
            'ref': "refs/heads/master",
        }
        res = hook_post(data, 'push')
        assert res.status_code == 200
        assert res.data == Responses.MASTER_PUSH_OK
        assert mock_dispatch.call_count == 1
        (event,) = mock_dispatch.call_args[0]
        assert isinstance(event, MasterMoved)
        assert event.data == {
            'owner': project.owner,
            'name': project.name,
        }

        pr_loaded = session.query(PullRequest).one()
        assert pr_loaded.ahead_of_master is None
        assert pr_loaded.behind_master is None


class TestPullRequest(object):
    @pytest.fixture(autouse=True)
    def project(self, session):
        project = Project(owner='my_owner', name='my_name')
        session.add(project)
        session.commit()
        return project

    def test_new(self, session, hook_post, mock_dispatch):
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
                'user': {
                    'login': 'me',
                },
                'head': {
                    'sha': '1',
                },
                'state': 'open',
                'base': {
                    'ref': 'master',
                },
            },
        }
        assert session.query(PullRequest).count() == 0

        res = hook_post(data, 'pull_request')
        assert res.status_code == 200
        assert res.data == Responses.PR_OK

        assert session.query(PullRequest).count() == 1
        assert mock_dispatch.call_count == 1
        (event,) = mock_dispatch.call_args[0]
        assert isinstance(event, PullRequestMoved)
        assert event.data == {
            'owner': 'my_owner',
            'name': 'my_name',
            'number': 1,
        }

    def test_ignore_not_against_master(self, session, hook_post, mock_dispatch):
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
                'user': {
                    'login': 'me',
                },
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
        assert mock_dispatch.call_count == 0

    def test_unknown_project(self, hook_post, session, mock_dispatch):
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
        assert mock_dispatch.call_count == 0
