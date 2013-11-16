from __future__ import absolute_import
import logging
import json

from flask import Blueprint, request

from .controllers import record_job_result, record_job_sha


logger = logging.getLogger(__name__)

jenkins = Blueprint('jenkins', __name__)


@jenkins.route('/api/build_status', methods=['POST'])
def build_status():
    """ Handle updates for jenkins status from the jenkins
    notifications plugin
    """
    logger.debug('receiving jenkins notification')

    data_str = request.get_data()


    """ Creates a Build from POST data

        data looks a little like this....
        {
          "name": "CInch",
          "url": "job/CInch/",
          "build": {
            "full_url": "http://***REMOVED***/job/CInch/2/",
            "number": 2,
            "phase": "STARTED",
            "url": "job/CInch/2/"
          }
        }

        {
          "name": "CInch",
          "url": "job/CInch/",
          "build": {
            "full_url": "http://***REMOVED***/job/CInch/3/",
            "number": 3,
            "phase": "FINISHED",
            "status": "SUCCESS",
            "url": "job/CInch/3/",
          }
        }

    """
    data = json.loads(data_str)
    build = data['build']

    if 'status' not in build:
        name = data['name']
        phase = build['phase']
        logger.info('build {} {}'.format(name, phase))
        return

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
