import pytest

from cinch.models import Project, Commit
from cinch.jenkins.models import JobType, Job
from cinch.jenkins.controllers import (
    get_jobs, record_job_result, record_job_sha, get_successful_builds,
    build_check)


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
    library = Project(name="library", repo_name='library')
    large_app = Project(name="large_app", repo_name='large_app')
    small_app = Project(name="small_app", repo_name='small_app')
    mobile = Project(name="mobile", repo_name='mobile')

    # job types
    unit = JobType(name="unit")
    integration = JobType(name="integration")

    # unit jobs
    library_unit = Job(name="library_unit", job_type=unit, projects=[library])
    large_app_unit = Job(name="large_app_unit", job_type=unit,
                         projects=[large_app])
    mobile_unit = Job(name="mobile_unit", job_type=unit, projects=[mobile])

    # integration jobs
    small_app_integration = Job(name="small_app_integration",
                                job_type=integration,
                                projects=[small_app, library])
    large_app_integration = Job(name="large_app_integration",
                                job_type=integration,
                                projects=[large_app, library])
    mobile_integration = Job(name="mobile_integration",
                             job_type=integration,
                             projects=[mobile, large_app, library])

    session.add(library)
    session.add(large_app)
    session.add(small_app)

    session.add(unit)
    session.add(integration)

    session.add(library_unit)
    session.add(large_app_unit)
    session.add(mobile_unit)

    session.add(large_app_integration)
    session.add(small_app_integration)
    session.add(mobile_integration)

    created = {obj.name: obj for obj in session.new}
    session.commit()

    return created


def test_get_jobs(fixtures):
    """
    """
    # library unit jobs
    assert get_jobs("library", "unit").one() == fixtures['library_unit']

    assert get_jobs("small_app", "unit").count() == 0
    assert get_jobs("small_app", "integration").all() == [
        fixtures['small_app_integration']
    ]

    assert get_jobs("large_app", "integration").all() == [
        fixtures['large_app_integration'],
        fixtures['mobile_integration'],
    ]

    assert get_jobs("library", "unit").count() == 1
    assert get_jobs("library", "integration").all() == [
        fixtures['large_app_integration'],
        fixtures['small_app_integration'],
        fixtures['mobile_integration'],
    ]


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


def test_get_successful_builds(session, fixtures):
    library_master = "lib-master-sha"

    # library@master passes unit tests
    shas = {
        'library': library_master
    }
    record_job_sha('library_unit', 1, 'library', library_master)
    record_job_result('library_unit', 1, True, "passed")

    build_shas = shas
    assert get_successful_builds('library', 'unit', build_shas) == [
        "library_unit"
    ]

    # small_app@sha1 integration passes against library@master
    shas = {
        'small_app': 'sha1',
        'library': library_master
    }
    record_job_sha('small_app_integration', 1, 'small_app', 'sha1')
    record_job_sha('small_app_integration', 1, 'library', library_master)
    record_job_result('small_app_integration', 1, True, "passed")

    build_shas = shas
    assert get_successful_builds('small_app', 'integration', build_shas) == [
        "small_app_integration"
    ]
    assert get_successful_builds('library', 'integration', build_shas) == [
        "small_app_integration"
    ]

    # large_app@sha2 integration passes against library@master
    shas = {
        'large_app': 'sha2',
        'library': library_master
    }
    record_job_sha('large_app_integration', 1, 'large_app', 'sha2')
    record_job_sha('large_app_integration', 1, 'library', library_master)
    record_job_result('large_app_integration', 1, True, "passed")

    build_shas = shas
    # large_app@sha2 has passed integration against library@master
    assert get_successful_builds('large_app', 'integration', build_shas) == [
        "large_app_integration"
    ]

    build_shas['small_app'] = "sha1"

    # small_app@sha1 has passed integration against library@master
    # large_app@sha2 has passed integration against library@master
    assert get_successful_builds('library', 'integration', build_shas) == [
        "large_app_integration",
        "small_app_integration"
    ]

    # small_app master is at sha1
    small_app = session.query(Project).filter_by(name="small_app").one()
    small_app.master_sha = "sha1"  # not a foreign key, so we can just write this
    session.commit()

    # so we can omit small_app for build_shas dict
    build_shas.pop('small_app')
    assert get_successful_builds('library', 'integration', build_shas) == [
        "large_app_integration",
        "small_app_integration"
    ]


def test_unit_test_check(fixtures):
    library_master = "lib-master-sha"

    # library@master passes unit tests
    record_job_sha('library_unit', 1, 'library', library_master)
    record_job_result('library_unit', 1, True, "passed")

    assert build_check("library", library_master, "unit")
    assert not build_check("library", "some_other_sha", "unit")
    assert not build_check("mobile", library_master, "unit")

    # mobile@sha1 passes unit tests
    record_job_sha('mobile_unit', 1, 'mobile', 'sha1')
    record_job_result('mobile_unit', 1, True, "passed")

    assert build_check("mobile", "sha1", "unit")
    assert not build_check("mobile", "some_other_sha", "unit")
    assert not build_check("mobile", library_master, "unit")


def record_job_shas(job_name, build_number, shas):
    for project_name, sha in shas.items():
        record_job_sha(job_name, build_number, project_name, sha)


def test_integration_test_check(session, fixtures):
    lib_sha = "lib-proposed-sha"

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
    assert not build_check('library', lib_sha, "integration")

    # large_app@sha2 integration passes against library@lib_sha
    shas = {
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('large_app_integration', 1, shas)
    record_job_result('large_app_integration', 1, True, "passed")

    # library integration not yet satisfied
    assert not build_check('library', lib_sha, "integration")

    # mobile@sha3 integration FAILS against library@lib_sha and large_app@sha2
    shas = {
        'mobile': 'sha3',
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('mobile_integration', 1, shas)
    record_job_result('mobile_integration', 1, False, "aborted")

    # library integration not yet satisfied
    assert not build_check('library', lib_sha, "integration")

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
    assert not build_check('library', lib_sha, "integration")

    # mobile@sha3 integration PASSES against library@lib_sha AND large_app@sha2
    shas = {
        'mobile': 'sha3',
        'large_app': 'sha2',
        'library': lib_sha
    }
    record_job_shas('mobile_integration', 3, shas)
    record_job_result('mobile_integration', 3, True, "passed")

    # library integration finally satisfied
    assert build_check('library', lib_sha, "integration")
