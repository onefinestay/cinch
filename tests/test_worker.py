from mock import patch
import pytest

from cinch.models import Project, PullRequest
from cinch.worker import RepoWorker


@pytest.yield_fixture(autouse=True)
def fake_repo():
    with patch('cinch.worker.Repo', autospec=True) as Repo:
        Repo.from_local_repo('owner', 'name').compare_pr.return_value = (
            None, None)
        yield Repo


class TestPush(object):
    @pytest.fixture(autouse=True)
    def project(self, session):
        project = Project(owner='my_owner', name='my_name')
        session.add(project)
        session.commit()
        return project

    def test_unseen_repo(self, fake_repo, session, project):
        pr1 = PullRequest(
            project=project, number=1, head='sha1', owner='me', title='foo',
            is_open=True,
        )
        session.add(pr1)
        session.commit()

        is_repo = fake_repo.from_local_repo('mock_owner', 'mock_name').is_repo
        is_repo.return_value = False

        setup_repo = fake_repo.setup_repo
        repo = setup_repo('mock_owner', 'mock_name')
        repo.compare_pr.return_value = (
            None, None)
        repo.is_mergeable.return_value = False
        repo.merge_head.return_value = None

        worker = RepoWorker()
        worker.master_moved({
            'name': 'my_name',
            'owner': 'my_owner',
        })
        assert setup_repo.call_count == 2  # once to set up mock, once in code
        args1, _ = setup_repo.call_args_list[0]
        args2, _ = setup_repo.call_args_list[1]
        assert args1 == ('mock_owner', 'mock_name')
        assert args2 == ('my_owner', 'my_name')

    def test_master_with_open_prs(self, session, project, fake_repo):
        pr1 = PullRequest(
            project=project, number=1, head='sha1', owner='me', title='foo',
            is_open=True
        )
        pr2 = PullRequest(
            project=project, number=2, head='sha2', owner='me', title='foo',
            is_open=True
        )
        pr3 = PullRequest(
            project=project, number=3, head='sha2', owner='me', title='foo',
            is_open=False
        )
        session.add(pr1)
        session.add(pr2)
        session.add(pr3)
        session.commit()

        repo = fake_repo.from_local_repo('owner', 'name')
        repo.is_mergeable.return_value = False
        repo.merge_head.return_value = None

        worker = RepoWorker()
        worker.master_moved({
            'name': 'my_name',
            'owner': 'my_owner',
        })
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

    def test_new(self, session, project, fake_repo):
        for number in [1, 2]:
            pr = PullRequest(
                project=project, number=number, head='sha1', owner='me',
                title='foo', is_open=True
            )
            session.add(pr)
        session.commit()

        repo = fake_repo.from_local_repo('owner', 'name')
        repo.is_mergeable.return_value = False

        worker = RepoWorker()
        worker.pull_request_moved({
            'name': 'my_name',
            'owner': 'my_owner',
            'number': 2,
        })
        assert repo.compare_pr.call_count == 1
        args, _ = repo.compare_pr.call_args_list[0]
        assert args == (2,)
