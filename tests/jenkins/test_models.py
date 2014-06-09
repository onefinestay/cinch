from cinch.jenkins.models import Build


def test_ordered_projects(fixtures):
    app_integration = fixtures['app_integration']

    projects = app_integration.ordered_projects()
    assert {p.name for p in projects} == {'app', 'library'}


def test_str(fixtures):
    app_integration = fixtures['app_integration']
    build = Build(job=app_integration, build_number=3)

    assert str(build) == "app_integration/3"
