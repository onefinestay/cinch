import inspect

_check_registry = []


def check(method):
    type_checks = _check_registry.append(method)
    return method


def run_checks(pull):
    for check in _check_registry:
        yield check(pull)
