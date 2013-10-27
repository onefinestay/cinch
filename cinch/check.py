import inspect

_check_registry = []


def check(method):
    type_checks = _check_registry.append(method)
    return method


def get_checks(obj):
    return _check_registry
