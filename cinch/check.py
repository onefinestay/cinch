import inspect

CHECK_REGISTRY_FLAG = '_check_registry_flag'


def check(method):
    setattr(method, CHECK_REGISTRY_FLAG, True)
    return method


def get_checks(obj):
    for _, attr in inspect.getmembers(obj, inspect.ismethod):
        if getattr(attr, CHECK_REGISTRY_FLAG, False):
            yield attr
