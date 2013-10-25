import logging
import json

from flask import request

from cinch.models import db, Job, Build

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()

logger.addHandler(ch)


def handle_data(data):
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
            "full_url": "http://***REMOVED***/job/CInch/2/",
            "number": 2,
            "phase": "COMPLETED",
            "status": "SUCCESS",
            "url": "job/CInch/2/"
          }
        } 

    """
    data = json.loads(data)

    build = data['build']
    if 'status' not in build:
        name = data['name'] 
        phase = build['phase']
        logger.info('build {} {}'.format(name, phase))
        return

    job_name = data['name']
    job_results = db.session.query(Job).filter_by(name=job_name)
    jobs = job_results.count()
    if not jobs:
        logger.info('Job {} does not exist')
        return

    build_number = build['number']
    job = job_results.one()
    status = build['status']
    success = True if status == 'SUCCESS' else False

    build = Build(
        build_number=build_number,
        job=job,
        success=success,
        status=status
    )

    db.session.add(build)
    db.session.commit()

    logger.info('created Build')
