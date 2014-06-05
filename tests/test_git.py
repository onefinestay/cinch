from mock import patch
import pytest

from cinch import app
from cinch.git import Repo

pytestmark = pytest.mark.slow


@pytest.yield_fixture(scope='module')
def tmp_base_dir(request):
    # builtin tmpdir fixture is function scoped :(
    tmpdir = request.config._tmpdirhandler.mktemp('cinch_repos')
    with patch.object(app, 'config', {'REPO_BASE_DIR': tmpdir.strpath}):
        yield
    tmpdir.remove()


@pytest.fixture(scope='module')
def repo(tmp_base_dir):
    repo = Repo.setup_repo('onefinestay', 'cinch')
    return repo


def test_compare(repo):
    _, ahead = repo.compare_pr(1)
    assert ahead == 0


def test_compare_unknown(repo):
    behind, ahead = repo.compare_pr(-1)
    assert (behind, ahead) == (None, None)


def test_fetch(repo):
    # nothing to return. should just not break
    assert repo.fetch() is None


def test_is_mergeable(repo):
    assert repo.is_mergeable(1)


def test_merge_head(repo):
    merge_head = repo.merge_head(1)
    assert merge_head is not None
