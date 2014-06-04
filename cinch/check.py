from collections import Iterable

_check_registry = []


class CheckStatus(object):
    """Wrapper for the result of checks

    Arguments:
        label: the label for the main dashboard
        status: (bool) success status
        verbose_name: more information about status (e.g. reason)
        url: url to page with more info around status (e.g. failed builds)
    """
    def __init__(self, label='', status=None, verbose_name='', url=None):
        self.label = label
        self.status = status
        self.verbose_name = verbose_name or label
        self.url = url or ''


def check(method):
    _check_registry.append(method)
    return method


def run_checks(pull):
    for check in _check_registry:
        check_retval = check(pull)
        if isinstance(check_retval, Iterable):
            for check_status in check_retval:
                yield check_status
        else:
            yield check_retval
