import json

import mock
import pytest

from cinch import app, db
from cinch.models import Project, PullRequest
from cinch.jenkins.models import Job
from cinch.jenkins import views
from cinch.jenkins.controllers import jenkins_check


views  # pyflakes


@pytest.fixture
def fixtures(session):

    library = Project(name="library", owner='owner')
    application = Project(name="application", owner='owner')

    session.add(library)
    session.add(application)

    app_integration = Job(
        name="app_integration",
        projects=[application, library],
    )

    session.add(app_integration)

    session.commit()


def test_record_sha(fixtures):
    client = app.test_client()
    data = {
        'job_name': 'app_integration',
        'build_number': 1,
        'project_name': 'application',
        'sha': 'sha1',
    }
    response = client.post('/jenkins/api/build_sha', data=data)
    assert response.status_code == 200


def make_jenkins_data(job_name, build_number, status='SUCCESS'):
    data = {
        "name": job_name,
        "url":  "http://jenkins.example.com/job/{}/".format(job_name),
        "build": {
            "full_url": "http://jenkins.example.com/job/app_integration/3/",
            "number": build_number,
            "phase": "FINISHED",
            "status": status,
            "url": "job/{}/{}/".format(job_name, build_number),
        },
    }
    return data


def test_record_status(fixtures):
    client = app.test_client()
    data = make_jenkins_data('app_integration', 2)
    response = client.post('/jenkins/api/build_status', data=json.dumps(data))
    assert response.status_code == 200


def test_build_with_shas(fixtures, app_context):
    client = app.test_client()
    data = {
        'job_name': 'app_integration',
        'build_number': 3,
        'project_name': 'application',
        'sha': 'sha1',
    }
    response = client.post('/jenkins/api/build_sha', data=data)
    assert response.status_code == 200

    data = {
        'job_name': 'app_integration',
        'build_number': 3,
        'project_name': 'library',
        'sha': 'sha2',
    }
    response = client.post('/jenkins/api/build_sha', data=data)
    assert response.status_code == 200


    data = make_jenkins_data('app_integration', 3)
    response = client.post('/jenkins/api/build_status', data=json.dumps(data))
    assert response.status_code == 200

    application = db.session.query(Project).filter_by(name='application').one()
    library = db.session.query(Project).filter_by(name='library').one()
    application.master_sha = 'sha1'
    library.master_sha = 'sha2'

    pull_request = PullRequest(
        is_open=True,
        number=1,
        project=application,
        head='sha1',
        owner='',
        title='',
    )
    db.session.add(pull_request)

    db.session.commit()

    # until we can figure out why url_for fails
    with mock.patch('cinch.jenkins.controllers.url_for'):
        statuses = [check.status for check in jenkins_check(pull_request)]
        assert all(statuses)
