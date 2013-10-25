from flask import g, request, render_template
import logging

from cinch import app, db
from cinch.auth.decorators import requires_auth
from cinch.jenkins import handle_data
from cinch.models import PullRequest

logger = logging.getLogger(__name__)


@app.route('/')
@requires_auth
def index():
    session = db.session
    pulls = session.query(PullRequest).all()
    return render_template('index.html')


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
