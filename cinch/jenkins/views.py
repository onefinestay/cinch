from __future__ import absolute_import
import json
import logging

from flask import Blueprint, request, abort, render_template
from sqlalchemy import desc

from cinch import db
from cinch.models import PullRequest, Project
from .controllers import record_job_result, record_job_sha, get_job_build_query
from .exceptions import UnknownProject, UnknownJob


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

    job_builds = {}
    jobs = pull_request_project.jobs
    for job in jobs:
        if pull_request_project not in job.projects:
            continue

        query, base_query, sha_columns = get_job_build_query(
            job.id,
            [project.id for project in job.projects],
            successful_only=False,
        )

        # build number, success, shas
        job_builds[job] = [
            (result[0], result[1], result[2:])
            for result in query.order_by(
                    desc(base_query.c.build_number)
                ).values(
                    base_query.c.build_number,
                    base_query.c.success,
                    *sha_columns
                )
        ]

    return render_template('jenkins/pull_request_status.html',
        pull_request=pull_request,
        jobs=jobs,
        job_builds=job_builds,
    )
