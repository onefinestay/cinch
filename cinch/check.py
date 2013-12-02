_check_registry = []


class CheckStatus(object):
    """
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
        yield check(pull)
