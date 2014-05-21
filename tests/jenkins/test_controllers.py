from collections import OrderedDict
from itertools import count

import pytest

from cinch.models import Project, Commit, PullRequest
from cinch.jenkins.models import Job
from cinch.jenkins.controllers import (
    record_job_result, record_job_sha, _all_open_prs, get_successful_job_shas
)

counter = count()

def has_successful_builds(pull_request, job):
    pr_map = _all_open_prs()
    job_number = pr_map[pull_request][job]
    return (job_number is not None)


def set_master(session, project_name, sha):
    project = session.query(Project).filter_by(name=project_name).one()
    project.master_sha = sha
    session.commit()  # TODO: needed?

def make_pr(session, project_name, sha):
    project = session.query(Project).filter_by(name=project_name).one()
    pull_request = PullRequest(
        is_open=True,
        number=next(counter),
        project=project,
        head_commit=sha,
        owner='',
        title='',
    )
    session.add(pull_request)
    session.commit()
    return pull_request


@pytest.fixture
def fixtures(session):
    """
    Dependency Graph:

    (library) <-[:DEPENDS_ON]- (small_app)
        ^
        '-------[:DEPENDS_ON]- (large_app) <-[:DEPENDS_ON]- (mobile)

    Impact Graph:

    (library) -[:IMPACTS]-> (small_app)
        ^
        '------[:IMPACTS]-> (large_app) -[:IMPACTS]-> (mobile)

    Test Suites:

    Unit: test a standalone project

        - library
        - large_app
        - mobile

    (small_app has no unit tests)

    Integration: test a project against the things it depends upon

        - small_app: test small_app against library
        - large_app: test large_app against library
        - mobile: test mobile against large_app and library
    """

    # projects
    library = Project(name="library", owner='owner')
    large_app = Project(name="large_app", owner='owner')
    small_app = Project(name="small_app", owner='owner')
    mobile = Project(name="mobile", owner='owner')

    # unit jobs
    library_unit = Job(name="library_unit", projects=[library])
    large_app_unit = Job(name="large_app_unit", projects=[large_app])
    mobile_unit = Job(name="mobile_unit", projects=[mobile])

    # integration jobs
    small_app_integration = Job(name="small_app_integration",
                                projects=[small_app, library])
    large_app_integration = Job(name="large_app_integration",
                                projects=[large_app, library])
    mobile_integration = Job(name="mobile_integration",
                             projects=[mobile, large_app, library])

    session.add(library)
    session.add(large_app)
    session.add(small_app)

    session.add(library_unit)
    session.add(large_app_unit)
    session.add(mobile_unit)

    session.add(large_app_integration)
    session.add(small_app_integration)
    session.add(mobile_integration)

    created = {obj.name: obj for obj in session.new}
    session.commit()

    return created


def test_record_job_result(session, fixtures):

    library_master = "lib-master-sha"

    # test small_app@sha1 against master library
    record_job_sha('small_app_integration', 1, 'small_app', 'sha1')
    record_job_sha('small_app_integration', 1, 'library', library_master)

    record_job_result('small_app_integration', 1, True, "passed")

    assert session.query(Commit).count() == 2
    assert session.query(Commit).get(library_master).project.name == "library"
    assert session.query(Commit).get("sha1").project.name == "small_app"

    # test large_app@sha2 against master library
    record_job_sha('large_app_integration', 1, 'large_app', 'sha2')
    record_job_sha('large_app_integration', 1, 'library', library_master)

    record_job_result('large_app_integration', 1, True, "passed")

    assert session.query(Commit).count() == 3
    assert session.query(Commit).get("sha2").project.name == "large_app"


def test_get_successful_builds(session, fixtures, app_context):
    library_unit = fixtures['library_unit']
    small_app_integration = fixtures['small_app_integration']

    library_master = "lib-master-sha"

    # library@master passes unit tests
    shas = {
        'library': library_master
    }

    record_job_sha('library_unit', 1, 'library', library_master)
    record_job_result('library_unit', 1, True, "passed")

    successful_job_shas = get_successful_job_shas({library_unit: shas})
    successful_shas = successful_job_shas[library_unit]
    assert successful_shas[(library_master,)] == 1

    # small_app@sha1 integration passes against library@master
    shas = OrderedDict([
        ('small_app', 'sha1'),
        ('library', library_master),
    ])
    record_job_sha('small_app_integration', 2, 'small_app', 'sha1')
    record_job_sha('small_app_integration', 2, 'library', library_master)
    record_job_result('small_app_integration', 2, True, "passed")

    # set_master(session, 'library', library_master)
    # small_app_pr = make_pr(session, 'small_app', 'sha1')

    # build_shas = shas
    # assert has_successful_builds(fixtures['small_app_integration'], build_shas)
    # import ipdb; ipdb.set_trace()
    # assert has_successful_builds(small_app_pr, fixtures['small_app_integration'])
    successful_job_shas = get_successful_job_shas(
        {small_app_integration: shas})
    successful_shas = successful_job_shas[small_app_integration]
    assert successful_shas[('sha1', library_master)] == 2




    # large_app@sha2 integration passes against library@master
    # shas = {
        # 'large_app': 'sha2',
        # 'library': library_master
    # }
    record_job_sha('large_app_integration', 3, 'large_app', 'sha2')
    record_job_sha('large_app_integration', 3, 'library', library_master)
    record_job_result('large_app_integration', 3, True, "passed")

    set_master(session, 'library', library_master)
    large_app_pr = make_pr(session, 'large_app', 'sha2')

    # build_shas = shas
    # large_app@sha2 has passed integration against library@master
    # assert has_successful_builds(fixtures['large_app_integration'], build_shas)
    assert has_successful_builds(large_app_pr, fixtures['large_app_integration'])

    # build_shas['small_app'] = "sha1"

    # small_app@sha1 has passed integration against library@master
    # large_app@sha2 has passed integration against library@master
    # assert has_successful_builds(fixtures['large_app_integration'], build_shas)
    # assert has_successful_builds(fixtures['small_app_integration'], build_shas)
    # assert has_successful_builds

    # small_app master is at sha1
    # small_app = session.query(Project).filter_by(name="small_app").one()
    # small_app.master_sha = "sha1"  # not a foreign key, so we can just write this
    # session.commit()
    set_master(session, 'small_app', 'sha1')

    # so we can omit small_app for build_shas dict
    # build_shas.pop('small_app')
    assert has_successful_builds(large_app_pr, fixtures['large_app_integration'])
    # assert has_successful_builds(small_app_pr, fixtures['small_app_integration'])


def record_job_shas(job_name, build_number, shas):
    for project_name, sha in shas.items():
        record_job_sha(job_name, build_number, project_name, sha)


def build_check(session, project_name, sha):
    pr = make_pr(session, project_name, sha)
    project = session.query(Project).filter_by(name=project_name).one()
    # shas = {project_name: sha}
    return all(
        has_successful_builds(pr, job)
        for job in project.jobs
    )


def test_integration_test_check(session, fixtures, app_context):
    lib_sha = "lib-proposed-sha"

    # library@proposed-sha passes unit tests
    record_job_sha('library_unit', 1, 'library', lib_sha)
    record_job_result('library_unit', 1, True, "passed")


    small_app = fixtures['small_app']
    large_app = fixtures['large_app']
    mobile = fixtures['mobile']

    # set project master_shas
    small_app.master_sha = "sha1"
    large_app.master_sha = "sha2"
    mobile.master_sha = "sha3"
    session.commit()

    # small_app@sha1 integration passes against library@lib_sha
    shas = {
        'small_app': 'sha1',
        'library': lib_sha
    }
    record_job_shas('small_app_integration', 1, shas)
    record_job_result('small_app_integration', 1, True, "passed")

    # library integration not yet satisfied
    assert not build_check(session, 'library', lib_sha)

    # large_app@sha2 integration passes against library@lib_sha
    shas = {
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('large_app_integration', 1, shas)
    record_job_result('large_app_integration', 1, True, "passed")

    # library integration not yet satisfied
    assert not build_check(session, 'library', lib_sha)

    # mobile@sha3 integration FAILS against library@lib_sha and large_app@sha2
    shas = {
        'mobile': 'sha3',
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('mobile_integration', 1, shas)
    record_job_result('mobile_integration', 1, False, "aborted")

    # library integration not yet satisfied
    assert not build_check(session, 'library', lib_sha)

    # mobile@sha3 integration PASSES against library@lib_sha,
    # but  against large_app@sha4
    shas = {
        'mobile': 'sha3',
        'large_app': 'sha4',
        'library': lib_sha
    }
    record_job_shas('mobile_integration', 2, shas)
    record_job_result('mobile_integration', 2, True, "passed")

    # library integration not yet satisfied
    assert not build_check(session, 'library', lib_sha)

    # mobile@sha3 integration PASSES against library@lib_sha AND large_app@sha2
    shas = {
        'mobile': 'sha3',
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('mobile_integration', 3, shas)
    record_job_result('mobile_integration', 3, True, "passed")

    # library integration finally satisfied
    assert build_check(session, 'library', lib_sha)
