from mock import patch
import pytest

from cinch import app


@patch('cinch.github.GithubUpdateHandler')
@pytest.mark.parametrize(('args', 'status_code', 'valid_update'), [
    ({}, 401, False),
    ({'secret': 'incorrect secret'}, 401, False),
    ({'secret': 'secret'}, 200, True),
])
def test_updates_require_secret(handler, args, status_code, valid_update):
    app.config['GITHUB_TOKEN'] = 'abc'
    app.config['GITHUB_UPDATE_SECRET'] = 'secret'

    with app.test_client() as client:
        res = client.post('/api/github/update', query_string=args, data={
            'payload': '{}',
        })

    assert res.status_code == status_code
    assert handler.called == valid_update
