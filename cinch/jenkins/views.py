from __future__ import absolute_import
from itertools import chain
import json
import logging

from flask import Blueprint, request, abort, render_template

from cinch import db
from cinch.models import PullRequest, Project
from .controllers import record_job_result, record_job_sha, get_jobs


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

    record_job_result(job_name, build_number, success, status)

    return 'OK', 200


@jenkins.route('/api/build_sha', methods=['POST'])
def build_sha():
    """ View for manual jenkins request to post shas for projects

    Example:
        $ PROJECT_NAME="my_project"
        $ SHA=$(git rev-parse HEAD)

        $ curl $CINCH -d "job_name=$JOB_NAME&build_number=$BUILD_NUMBER\
            project_name=$PROJECT_NAME&sha=$SHA
    """
    logger.debug('receiving jenkins shas')

    form = request.form
    record_job_sha(
        form['job_name'],
        form['build_number'],
        form['project_name'],
        form['sha'],
    )

    return 'OK', 200


@jenkins.route('/pr/<project_name>/<pr_number>')
def pull_request_status(project_name, pr_number):
    pull_request = db.session.query(PullRequest).join(Project).filter(
        PullRequest.number == pr_number,
        Project.name == project_name).first()

    if pull_request is None:
        abort(404, "Unknown pull request")

    unit_jobs = get_jobs(pull_request.project.name, 'unit')
    integration_jobs = get_jobs(pull_request.project.name, 'integration')

    jobs = chain(unit_jobs, integration_jobs)

    return render_template('jenkins/pull_request_status.html',
        pull_request=pull_request,
        jobs=jobs,
    )
