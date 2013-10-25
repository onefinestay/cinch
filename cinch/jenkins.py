import logging
import json

from flask import request

from cinch.auth import requires_auth
from cinch.models import db, Job

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()

logger.addHandler(ch)


def handle_data(data):
    """ Creates a Build from POST data

        data looks a little like this....
        {
          "name": "***REMOVED***_unit",
          "url": "job/***REMOVED***_unit/",
          "build": {
            "full_url": "http://***REMOVED***/job/***REMOVED***_unit/1954/",
            "number": 1954,
            "phase": "STARTED",
            "url": "job/***REMOVED***_unit/1954/",
            "parameters": {
              "PLATFORM_REVISION": "master"
            }
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
    job = db.session.query(Job).filter_by(name='name')
    if not job:
        logger.info('Job {} does not exist')
        return

    build_number = build['number']
    result = data['status']

    build = Build(
        build_number=build_number,
        job=job,
        result=result
    )
    db.session.add(build)
    db.commit()

    logger.info('created Build')

    
    

