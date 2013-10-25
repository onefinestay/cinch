import pytest

from cinch.models import Project, JobType, Job, Commit
from cinch.controllers import get_jobs, record_job_result


@pytest.fixture(scope='session')
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

    assert get_jobs("library", "unit").count() == 1
    assert get_jobs("library", "integration").all() == [
        fixtures['large_app_integration'],
        fixtures['small_app_integration'],
        fixtures['mobile_integration'],
    ]


def test_record_job_result(session, fixtures):

    library_master = "lib-master-sha"

    # test small_app@sha1 against master library
    shas = {
        'small_app': 'sha1',
        'library': library_master
    }
    record_job_result('small_app_integration', 1, shas, True, "passed")

    assert session.query(Commit).count() == 2
    assert session.query(Commit).get(library_master).project.name == "library"
    assert session.query(Commit).get("sha1").project.name == "small_app"

    # test large_app@sha2 against master library
    shas = {
        'large_app': 'sha2',
        'library': library_master
    }
    record_job_result('large_app_integration', 1, shas, True, "passed")

    assert session.query(Commit).count() == 3
    assert session.query(Commit).get("sha2").project.name == "large_app"


def test_get_successful_builds(session, fixtures):

    # small_app@sha1 passes against library master
    library_master = "lib-master-sha"
    shas = {
        'small_app': 'sha1',
        'library': library_master
    }
    record_job_result('small_app_integration', 1, shas, True, "passed")
    # UNFINSHED






