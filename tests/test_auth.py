from urllib import quote_plus, urlencode

from cinch import app


def test_requires_auth_decorator():
    tester = app.test_client()
    response = tester.get('/pull_request/foo/bar/1')

    assert response.status_code == 302  # redirect
    assert '/login' in response.location
    assert '?next=' in response.location
    assert quote_plus('/pull_request/foo/bar/1')  in response.location


def test_github_auth_redirect():
    tester = app.test_client()

    response = tester.get('/login?next={}'.format(quote_plus('/pull_request/foo/bar/1')))

    assert response.status_code == 302  # redirect
    assert 'github.com/login/oauth/authorize' in response.location  # redirecting to github
    assert quote_plus('/callback') in response.location  # with the callback url being the callback route
    assert quote_plus(urlencode({'next': '/pull_request/foo/bar/1'})) in response.location  # quoting plus since its a parameter in a parameter
