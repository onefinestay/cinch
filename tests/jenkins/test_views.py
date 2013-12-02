import json

import pytest

from cinch import app, db
from cinch.models import Project
from cinch.jenkins.models import Job
from cinch.jenkins.controllers import build_check


@pytest.fixture
def fixtures(session):

    library = Project(name="library", repo_name='library')
    application = Project(name="application", repo_name='application')

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


def test_build_with_shas(fixtures):
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

    db.session.commit()

    assert build_check('application', 'sha1')
