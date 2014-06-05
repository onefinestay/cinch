import json

from flask import url_for

from cinch import db
from cinch.models import PullRequest
from cinch.jenkins import views
from cinch.jenkins.controllers import jenkins_check

views  # pyflakes


def test_record_sha(fixtures, app_context):
    client = app_context.test_client()
    data = {
        'job_name': 'app_integration',
        'build_number': 1,
        'project_owner': 'owner',
        'project_name': 'app',
        'sha': 'sha1',
    }
    url = url_for('jenkins.build_sha')
    response = client.post(url, data=data)
    assert response.status_code == 200


def test_record_sha_unknown_job(fixtures, app_context):
    client = app_context.test_client()
    data = {
        'job_name': 'foo',
        'build_number': 1,
        'project_owner': 'owner',
        'project_name': 'app',
        'sha': 'sha1',
    }
    url = url_for('jenkins.build_sha')
    response = client.post(url, data=data)
    assert response.status_code == 404


def test_record_sha_unknown_project(fixtures, app_context):
    client = app_context.test_client()
    data = {
        'job_name': 'app_unit',
        'build_number': 1,
        'project_owner': 'owner',
        'project_name': 'bar',
        'sha': 'sha1',
    }
    url = url_for('jenkins.build_sha')
    response = client.post(url, data=data)
    assert response.status_code == 404


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


def test_record_status(fixtures, app_context):
    client = app_context.test_client()
    data = make_jenkins_data('app_integration', 2)
    url = url_for('jenkins.build_status')
    response = client.post(url, data=json.dumps(data))
    assert response.status_code == 200


def test_record_status_unknown_job(fixtures, app_context):
    client = app_context.test_client()
    data = make_jenkins_data('app_integration', 2)
    data['name'] = 'foo'
    url = url_for('jenkins.build_status')
    response = client.post(url, data=json.dumps(data))
    assert response.status_code == 404


def test_build_with_shas(fixtures, app_context):
    client = app_context.test_client()
    data = {
        'job_name': 'app_integration',
        'build_number': 3,
        'project_owner': 'owner',
        'project_name': 'app',
        'sha': 'sha1',
    }
    url = url_for('jenkins.build_sha')
    response = client.post(url, data=data)
    assert response.status_code == 200

    data = {
        'job_name': 'app_integration',
        'build_number': 3,
        'project_owner': 'owner',
        'project_name': 'library',
        'sha': 'sha2',
    }
    url = url_for('jenkins.build_sha')
    response = client.post(url, data=data)
    assert response.status_code == 200

    data = make_jenkins_data('app_integration', 3)
    url = url_for('jenkins.build_status')
    response = client.post(url, data=json.dumps(data))
    assert response.status_code == 200

    app = fixtures['app']
    library = fixtures['library']
    app.master_sha = 'sha1'
    library.master_sha = 'sha2'

    pull_request = PullRequest(
        is_open=True,
        number=1,
        project=app,
        head='sha1',
        owner='',
        title='',
    )
    db.session.add(pull_request)

    db.session.commit()

    statuses = [
        check.status for check in jenkins_check(pull_request)
        if 'app_integration' in check.label
    ]
    assert statuses == [True]


def test_pull_request_view(fixtures, app_context):
    app = fixtures['app']

    pull_request = PullRequest(
        is_open=True,
        number=1,
        project=app,
        head='sha1',
        owner='',
        title='',
    )
    db.session.add(pull_request)
    db.session.commit()

    client = app_context.test_client()
    url = url_for(
        'jenkins.pull_request_status',
        project_owner='owner',
        project_name='app',
        pr_number='1',
    )
    response = client.get(url)
    assert response.status_code == 200
