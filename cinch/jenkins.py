import logging
import json

from cinch.controllers import record_job_result

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
            "full_url": "http://***REMOVED***/job/CInch/3/",
            "number": 3,
            "phase": "FINISHED",
            "status": "SUCCESS",
            "url": "job/CInch/3/",
            "parameters": {
              "CINCH_SHA": "master"
            }
          }
        }

    """
    data = json.loads(data)
    build = data['build']

    if 'parameters' not in build:
        raise Exception('This is not a parametarized build')

    if 'status' not in build:
        name = data['name'] 
        phase = build['phase']
        logger.info('build {} {}'.format(name, phase))
        return

    job_name = data['name']
    build_number = build['number']
    shas = {
        key[:-4].lower(): value
        for key, value in build['parameters'].items()
            if key.endswith('_SHA')
    }

    status = build['status']
    success = True if status == 'SUCCESS' else False

    record_job_result(job_name, build_number, shas, success, status)

    logger.info('created Build')
