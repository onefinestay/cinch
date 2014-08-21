from collections import OrderedDict
from itertools import count

from mock import patch
from sqlalchemy import event
from sqlalchemy.engine import Engine

from cinch.models import Project, PullRequest
from cinch.jenkins.models import Job, BuildSha
from cinch.jenkins.controllers import (
    clear_g_cache, record_job_result, record_job_sha, all_open_prs,
    get_job_sha_statuses, jenkins_check, get_or_create_build, get_prs_for_build
)

counter = count()


class QueryCounter():
    def __init__(self):
        self.count = 0

    def __enter__(self):
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(*args, **kwargs):
            self.count += 1

        self.listener = after_cursor_execute

        return self

    def __exit__(self, *args, **kwargs):
        event.remove(Engine, "after_cursor_execute", self.listener)


def has_successful_builds(pull_request, job):
    clear_g_cache()
    pr_map = all_open_prs()
    job_number = pr_map[pull_request][job]
    return (job_number is not None)


def set_master(session, project_name, sha):
    project = session.query(Project).filter_by(name=project_name).one()
    project.master_sha = sha


def make_pr(session, project_name, sha):
    project = session.query(Project).filter_by(name=project_name).one()
    pull_request = PullRequest(
        is_open=True,
        number=next(counter),
        project=project,
        head=sha,
        owner='',
        title='',
    )
    session.add(pull_request)
    session.commit()
    return pull_request


def get_shas(job, shas):
    """Test helper for checking single jobs"""
    job_shas = get_job_sha_statuses({job: shas})
    assert len(job_shas) == 1
    assert job in job_shas
    return job_shas[job]


def test_record_job_result(session, fixtures):

    library_master = "lib-master-sha"

    # test app@sha1 against master library
    record_job_sha('app_integration', 1, 'owner', 'app', 'sha1')
    record_job_sha('app_integration', 1, 'owner', 'library', library_master)

    record_job_result('app_integration', 1, True, "passed")

    assert session.query(BuildSha).count() == 2
    assert session.query(BuildSha).filter_by(
        sha=library_master).one().project.name == "library"
    assert session.query(BuildSha).filter_by(
        sha="sha1").one().project.name == "app"

    # test app@sha2 against master library
    record_job_sha('app_integration', 2, 'owner', 'app', 'sha2')
    record_job_sha('app_integration', 2, 'owner', 'library', library_master)

    record_job_result('app_integration', 2, True, "passed")

    assert session.query(BuildSha).count() == 4
    assert session.query(BuildSha).filter_by(
        sha="sha2").one().project.name == "app"


def test_get_prs_for_build(session, fixtures):

    set_master(session, 'app', 'sha1')
    set_master(session, 'library', 'sha2')

    app_pr = make_pr(session, project_name='app', sha='1234')

    with patch('cinch.jenkins.controllers.dispatcher') as dispatcher:
        with dispatcher() as dispatch:
            pass

        record_job_sha('app_integration', 1, 'owner', 'library', 'sha2')
        assert dispatch.call_count == 0

        record_job_sha('app_integration', 1, 'owner', 'app', '1234')
        assert dispatch.call_count == 1

        record_job_result('app_integration', 1, True, "passed")
        assert dispatch.call_count == 2

    job = session.query(Job).filter(Job.name == 'app_integration').one()
    build = get_or_create_build(job, 1)
    prs = get_prs_for_build(build).all()

    assert len(prs) == 1
    assert prs[0] == app_pr


def test_multiple_prs_for_build(session, fixtures):

    set_master(session, 'app', 'sha1')
    set_master(session, 'library', 'sha2')

    app_pr = make_pr(session, project_name='app', sha='1234')
    library_pr = make_pr(session, project_name='library', sha='2345')

    with patch('cinch.jenkins.controllers.dispatcher') as dispatcher:
        with dispatcher() as dispatch:
            pass

        record_job_sha('app_integration', 1, 'owner', 'app', '1234')
        assert dispatch.call_count == 1

        record_job_sha('app_integration', 1, 'owner', 'library', '2345')
        # both pull requests will be recorded from this point
        assert dispatch.call_count == 3

        record_job_result('app_integration', 1, True, "passed")
        assert dispatch.call_count == 5

    job = session.query(Job).filter(Job.name == 'app_integration').one()
    build = get_or_create_build(job, 1)
    prs = get_prs_for_build(build).all()

    assert len(prs) == 2
    assert app_pr in prs
    assert library_pr in prs


class TestGetSuccessfulJobShas(object):
    def test_single_project_job(self, fixtures):
        library = fixtures['library']

        # library@sha1 passes unit tests
        record_job_sha('library_unit', 1, 'owner', 'library', 'sha1')
        record_job_result('library_unit', 1, True, "passed")

        shas = OrderedDict([
            (library.id, 'sha1'),
        ])
        successful = get_shas(
            fixtures['library_unit'].id,
            shas,
        )
        assert successful == {
            ('sha1',): (1, True),
        }

    def test_multi_project_job(self, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        # app@sha2 integration passes against library@sha3
        shas = OrderedDict([
            (app.id, ''),
            (library.id, ''),
        ])
        record_job_sha('app_integration', 2, 'owner', 'app', 'sha2')
        record_job_sha('app_integration', 2, 'owner', 'library', 'sha3')
        record_job_result('app_integration', 2, True, "passed")

        successful = get_shas(fixtures['app_integration'].id, shas)
        assert successful[('sha2', 'sha3')] == (2, True)

    def test_multiple_builds(self, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        shas = OrderedDict([
            (app.id, ''),
            (library.id, ''),
        ])
        record_job_sha('app_integration', 2, 'owner', 'app', 'sha2')
        record_job_sha('app_integration', 2, 'owner', 'library', 'sha3')
        record_job_result('app_integration', 2, True, "passed")

        record_job_sha('app_integration', 4, 'owner', 'app', 'sha4')
        record_job_sha('app_integration', 4, 'owner', 'library', 'sha5')
        record_job_result('app_integration', 4, True, "passed")

        successful = get_shas(fixtures['app_integration'].id, shas)
        assert successful == {
            ('sha2', 'sha3'): (2, True),
            ('sha4', 'sha5'): (4, True),
        }

    def test_unsuccesful_builds(self, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        shas = OrderedDict([
            (app.id, ''),
            (library.id, ''),
        ])
        record_job_sha('app_integration', 2, 'owner', 'app', 'sha2')
        record_job_sha('app_integration', 2, 'owner', 'library', 'sha3')
        record_job_result('app_integration', 2, True, "passed")

        record_job_sha('app_integration', 4, 'owner', 'app', 'sha4')
        record_job_sha('app_integration', 4, 'owner', 'library', 'sha5')
        record_job_result('app_integration', 4, False, "passed")

        sha_statuses = get_shas(fixtures['app_integration'].id, shas)
        assert sha_statuses == {
            ('sha2', 'sha3'): (2, True),
            ('sha4', 'sha5'): (4, False),
        }


    def test_other_job_ignored(self, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        # library@sha1 passes unit tests
        record_job_sha('library_unit', 1, 'owner', 'library', 'sha1')
        record_job_result('library_unit', 1, True, "passed")

        library_unit = fixtures['library_unit']
        app_unit = fixtures['app_unit']
        successful_job_shas = get_job_sha_statuses({
            library_unit.id: {
                library.id: '',
            },
            app_unit.id: {
                app.id: '',
            },
        })
        assert successful_job_shas[library_unit.id] == {
            ('sha1',): (1, True),
        }
        assert successful_job_shas[app_unit.id] == {}

    def test_separate_builds_with_same_number(self, session, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        shas = OrderedDict([
            (app.id, ''),
            (library.id, ''),
        ])

        app_integration = fixtures['app_integration']
        app_integration2 = Job(
            name="app_integration2",
            projects=[app, library])

        session.add(app_integration2)
        session.commit()

        record_job_sha('app_integration', 1, 'owner', 'app', 'sha2')
        record_job_sha('app_integration', 1, 'owner', 'library', 'sha3')
        record_job_result('app_integration', 1, True, "passed")

        record_job_sha('app_integration2', 1, 'owner', 'app', 'sha4')
        record_job_sha('app_integration2', 1, 'owner', 'library', 'sha5')
        record_job_result('app_integration2', 1, True, "passed")

        successful = get_job_sha_statuses({
            app_integration.id: shas,
            app_integration2.id: shas,
        })
        assert successful == {
            app_integration.id: {
                ('sha2', 'sha3'): (1, True),
            },
            app_integration2.id: {
                ('sha4', 'sha5'): (1, True)
            },
        }

    def test_one_query_per_job(self, session, fixtures):
        n_queries = [0]
        foo = []


        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(*args, **kwargs):
            foo.append((args, kwargs))
            n_queries[0] += 1

        for x in range(20):
            record_job_sha(
                'app_integration', x, 'owner', 'app', 'shax{}'.format(x))
            record_job_sha(
                'app_integration', x, 'owner', 'library', 'shay{}'.format(x))
            record_job_result('app_integration', x, True, "passed")

        library = fixtures['library']
        app = fixtures['app']

        app_integration_id = fixtures['app_integration'].id
        app_unit_id = fixtures['app_unit'].id
        shas = OrderedDict([
            (app.id, ''),
            (library.id, ''),
        ])

        # single job
        with QueryCounter() as qc:
            get_job_sha_statuses({app_integration_id: shas})
        assert qc.count == 1

        # 2 jobs
        with QueryCounter() as qc:
            get_job_sha_statuses({
                app_integration_id: shas,
                app_unit_id: shas,
            })
        assert qc.count == 2

        # jobs with no projects
        with QueryCounter() as qc:
            get_job_sha_statuses({
                app_integration_id: {},
                app_unit_id: {},
            })
        assert qc.count == 2


def build_checks(session, project_name, sha, job_name=None):
    clear_g_cache()
    pr = make_pr(session, project_name, sha)
    def match(check):
        if job_name is None:
            return True
        return job_name in check.label

    return [
        check.status for check in jenkins_check(pr)
        if match(check)
    ]


def test_integration_test_check(session, fixtures, app_context):
    lib_sha = "lib-proposed-sha"

    # library@proposed-sha passes unit tests
    record_job_sha('library_unit', 1, 'owner', 'library', lib_sha)
    record_job_result('library_unit', 1, True, "passed")

    app = fixtures['app']

    # set project master_shas
    app.master_sha = "sha1"
    session.commit()

    # library integration not yet satisfied
    assert not all(build_checks(session, 'library', lib_sha))

    # app@sha1 integration passes against library@lib_sha
    record_job_sha('app_integration', 1, 'owner', 'app', 'sha1')
    record_job_sha('app_integration', 1, 'owner', 'library', lib_sha)
    record_job_result('app_integration', 1, True, "passed")

    # library integration now satisfied
    assert all(build_checks(session, 'library', lib_sha))


def test_statuses(session, fixtures, app_context):
    lib_sha = "lib-proposed-sha"

    # unknown
    assert build_checks(session, 'library', lib_sha, 'library_unit') == [None]

    record_job_sha('library_unit', 1, 'owner', 'library', lib_sha)
    # still unknown
    assert build_checks(session, 'library', lib_sha, 'library_unit') == [None]

    # succeeded
    record_job_result('library_unit', 1, True, "")
    assert build_checks(session, 'library', lib_sha, 'library_unit') == [True]

    # failed
    record_job_result('library_unit', 1, False, "")
    assert build_checks(session, 'library', lib_sha, 'library_unit') == [False]


def test_check_no_jobs(session, app_context):
    project = Project(name='foo', owner='bar')
    session.add(project)
    session.commit()

    assert build_checks(session, 'foo', 'sha') == []


# regression test
def test_dont_match_if_merge_head_is_none(session, fixtures, app_context):
    # no shas recorded
    record_job_result('library_unit', 1, True, "passed")

    clear_g_cache()
    pr = make_pr(session, 'library', 'sha')
    pr.merge_head = None

    statuses = [
        check.status for check in jenkins_check(pr)
        if 'library_unit' in check.label
    ]
    assert statuses == [None]
