import json

from flask import url_for
from mock import patch

from cinch import db
from cinch.models import PullRequest
from cinch.jenkins import views
from cinch.jenkins.controllers import (
    clear_g_cache, record_job_sha, record_job_result)

views  # pyflakes


def job_status(app_context, pull_request, job_name):
    clear_g_cache()
    client = app_context.test_client()
    url = url_for(
        'jenkins.pull_request_status',
        project_owner=pull_request.project.owner,
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )
    with patch('cinch.jenkins.views.render_template') as render:
        render.return_value = ''
        client.get(url)
    args, kwargs = render.call_args
    job_statuses = kwargs['job_statuses']
    job_status_map = {
        job_status['job_name']: job_status['status']
        for job_status in job_statuses
    }
    return job_status_map[job_name]



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

    assert job_status(app_context, pull_request, 'app_integration') is True


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


def test_statuses(session, fixtures, app_context):
    library = fixtures['library']
    lib_sha = "lib-proposed-sha"

    pull_request = PullRequest(
        is_open=True,
        number=1,
        project=library,
        head=lib_sha,
        owner='',
        title='',
    )
    db.session.add(pull_request)
    db.session.commit()

    # unknown
    assert job_status(app_context, pull_request, 'library_unit') is None

    record_job_sha('library_unit', 1, 'owner', 'library', lib_sha)
    # still unknown
    assert job_status(app_context, pull_request, 'library_unit') is None

    # succeeded
    record_job_result('library_unit', 1, True, "")
    assert job_status(app_context, pull_request, 'library_unit') is True

    # failed
    record_job_result('library_unit', 1, False, "")
    assert job_status(app_context, pull_request, 'library_unit') is False
