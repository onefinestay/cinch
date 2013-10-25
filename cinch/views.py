
import logging

from flask import g, request

from cinch import app
from cinch.auth.decorators import requires_auth
from cinch.jenkins import handle_data

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    message = """
        <p>Hello World!<br>CI is a cinch!<br>
             <a href="/login/">login</a></br>
             <a href="/logout/">logout</a></br>
             <a href="/user">you</a></br>
             <a href="/secret/">secret</a>
        </p>"""

    return message


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token


@app.route('/api/jenkins/pull', methods=['POST'])
def accept_jenksins_update():
    """ View for jenkins web hooks to handle updates
    """
    logger.debug('receiving jenkins notification')

    data = request.get_data()
    try:
        handle_data(data)
    except Exception, e:
        logger.error(str(e), exc_info=True)
        raise

    return 'OK', 200
