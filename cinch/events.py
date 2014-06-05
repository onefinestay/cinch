from nameko.containers import MAX_WORKERS_CONFIG_KEY
from nameko.events import Event
from nameko.messaging import AMQP_URI_CONFIG_KEY

from cinch import app


class MasterMoved(Event):
    type = 'master_moved'


class PullRequestMoved(Event):
    type = 'pull_request_moved'


def get_nameko_config():
    amqp_uri = app.config.get('NAMEKO_AMQP_URI')

    if not amqp_uri:
        raise RuntimeError(
            'NAMEKO_AMQP_URI must be configured in order to run this worker'
        )

    return {
        AMQP_URI_CONFIG_KEY: amqp_uri,

        # we're not threadsafe, but don't need concurrency, only async
        MAX_WORKERS_CONFIG_KEY: 1,
    }
