from __future__ import absolute_import
import json
import logging

from flask import Blueprint, request, abort, render_template, url_for
import requests
from sqlalchemy.orm.exc import NoResultFound

from cinch import app, db
from cinch.exceptions import UnknownProject
from cinch.models import PullRequest, Project
from .controllers import record_job_result, record_job_sha, all_open_prs
from .exceptions import UnknownJob
from .models import Job, JobProject


logger = logging.getLogger(__name__)

jenkins = Blueprint('jenkins', __name__)


@jenkins.route('/api/build_status', methods=['POST'])
def build_status():
    """ Handle updates for jenkins status from the jenkins
    notifications plugin
    """
    logger.debug('receiving jenkins notification')

    data_str = request.get_data()
    data = json.loads(data_str)
    build = data['build']

    if 'status' not in build:
        name = data['name']
        phase = build['phase']
        logger.info('build {} {}'.format(name, phase))
        return 'OK', 200

    job_name = data['name']
    build_number = build['number']

    status = build['status']
    success = (status == 'SUCCESS')

    try:
        record_job_result(job_name, build_number, success, status)
    except UnknownJob:
        return "Unknown job {}".format(job_name), 404

    return 'OK', 200


@jenkins.route('/api/build_sha', methods=['POST'])
def build_sha():
    """ View for manual jenkins request to post shas for projects

    Example:
        $ PROJECT_OWNER="me"
        $ PROJECT_NAME="my_project"
        $ SHA=$(git rev-parse HEAD)

        $ curl $CINCH -d "job_name=$JOB_NAME&build_number=$BUILD_NUMBER\
            project_owner=$PROJECT_OWNER&project_name=$PROJECT_NAME&sha=$SHA
    """
    logger.debug('receiving jenkins shas')

    form = request.form
    job_name = form['job_name']
    project_owner = form['project_owner']
    project_name = form['project_name']
    try:
        record_job_sha(
            job_name,
            form['build_number'],
            project_owner,
            project_name,
            form['sha'],
        )
    except UnknownProject:
        return "Unknown project {}/{}".format(
            project_owner, project_name), 404
    except UnknownJob:
        return "Unknown job {}".format(job_name), 404

    return 'OK', 200


@jenkins.route('/pr/<project_owner>/<project_name>/<pr_number>')
def pull_request_status(project_owner, project_name, pr_number):
    session = db.session

    pull_request = session.query(PullRequest).join(Project).filter(
        PullRequest.number == pr_number,
        Project.owner == project_owner, Project.name == project_name
    ).first()

    if pull_request is None:
        abort(404, "Unknown pull request")

    pull_request_project = pull_request.project

    pr_map = all_open_prs()
    jobs = pull_request_project.jobs

    job_statuses = []
    jenkins_url = app.config.get('JENKINS_URL', 'http://jenkins.example.com')

    for job in sorted(jobs, key=lambda j: j.name):
        build_number, status = pr_map[pull_request][job.id]

        if build_number is None:
            status = None
            label = job.name
            url = None
        else:
            label = "{}: {}".format(job.name, build_number)
            url = "{}/job/{}/{}/".format(jenkins_url, job.name, build_number)

        job_statuses.append(
            dict(
                label=label,
                status=status,
                url=url,
                job_name=job.name,
            )
        )

    return render_template(
        'jenkins/pull_request_status.html',
        pull_request=pull_request,
        job_statuses=job_statuses,
        rebuild_url=url_for('jenkins.trigger_build'),
    )


@jenkins.route('/api/jobs/trigger', methods=['POST'])
def trigger_build():
    session = db.session

    form = request.form
    job_name = form['job_name']
    project_owner = form['project_owner']
    project_name = form['project_name']
    pull_request_number = form['pull_request_number']

    try:
        job = session.query(Job).filter(Job.name == job_name).one()
    except NoResultFound:
        abort(404, 'Unknown job name {}'.format(job_name))

    try:
        pr = session.query(PullRequest).join(Project) .filter(
            Project.owner == project_owner,
            Project.name == project_name,
            PullRequest.number == pull_request_number,
        ).one()
    except NoResultFound:
        abort(404, "Unknown pull request {}/{}/{}".format(
            project_owner, project_name, pull_request_number))


    shas = {}
    shas = {
        project: project.master_sha
        for project in job.projects
    }
    shas[pr.project] = pr.merge_head

    job_params = session.query(JobProject).filter(
        JobProject.job_id == job.id).all()
    parameter_names = {
        param.project_id: param.parameter_name
        for param in job_params
    }
    jenkins_params = {
        parameter_names.get(project.id, project.name): sha
        for project, sha in shas.items()
    }

    jenkins_url = app.config.get('JENKINS_URL', 'http://jenkins.example.com')
    trigger_url = "{}/job/{}/buildWithParameters".format(jenkins_url, job.name)
    requests.post(trigger_url, data=jenkins_params)
    # print trigger_url, jenkins_params
    return "ok"
