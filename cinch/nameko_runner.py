"""Entry point for running the worker. In a separate module, since this
requires eventlet monkey patching which we don't want anywhere else.
"""

import eventlet
eventlet.monkey_patch()

from nameko.runners import ServiceRunner

from cinch.worker import get_nameko_config, RepoWorker


def run_worker():
    config = get_nameko_config()

    service_runner = ServiceRunner(config)
    service_runner.add_service(RepoWorker)

    service_runner.start()
    service_runner.wait()


if __name__ == '__main__':
    run_worker()
