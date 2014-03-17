from mock import patch
import pytest

from cinch import app


@patch('cinch.github.GithubUpdateHandler')
@pytest.mark.parametrize(('args', 'status_code'), [
    ({}, 401),
    ({'secret': 'incorrect secret'}, 401),
    ({'secret': 'secret'}, 200),
])
def test_updates_require_secret(handler, args, status_code):
    app.config['GITHUB_TOKEN'] = 'abc'
    app.config['GITHUB_UPDATE_SECRET'] = 'secret'

    with app.test_client() as client:
        res = client.post('/api/github/update', query_string=args, data={
            'payload': '{}',
        })

    assert res.status_code == status_code
    assert handler.called == (status_code == 200)
