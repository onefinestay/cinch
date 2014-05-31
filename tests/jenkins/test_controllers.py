from collections import OrderedDict
from itertools import count

from flask import g
from sqlalchemy import event
from sqlalchemy.engine import Engine

from cinch.models import Project, PullRequest
from cinch.jenkins.models import Job, BuildSha
from cinch.jenkins.controllers import (
    record_job_result, record_job_sha, _all_open_prs, get_successful_job_shas,
    jenkins_check,
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
        head=sha,
        owner='',
        title='',
    )
    session.add(pull_request)
    session.commit()
    return pull_request

def get_successful_shas(job, shas):
    """Test helper for checking single jobs"""
    successful_job_shas = get_successful_job_shas({job: shas})
    assert len(successful_job_shas) == 1
    assert job in successful_job_shas
    return successful_job_shas[job]


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


class TestGetSuccessfulJobShas(object):
    def test_single_project_job(self, fixtures):
        library = fixtures['library']

        # library@sha1 passes unit tests
        record_job_sha('library_unit', 1, 'owner', 'library', 'sha1')
        record_job_result('library_unit', 1, True, "passed")

        shas = OrderedDict([
            (library.id, 'sha1'),
        ])
        successful = get_successful_shas(
            fixtures['library_unit'].id,
            shas,
        )
        assert successful == {
            ('sha1',): 1,
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

        successful = get_successful_shas(fixtures['app_integration'].id, shas)
        assert successful[('sha2', 'sha3')] == 2

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

        successful = get_successful_shas(fixtures['app_integration'].id, shas)
        assert successful == {
            ('sha2', 'sha3'): 2,
            ('sha4', 'sha5'): 4,
        }

    def test_unsuccesful_builds_ignored(self, fixtures):
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

        successful = get_successful_shas(fixtures['app_integration'].id, shas)
        assert successful == {
            ('sha2', 'sha3'): 2,
        }


    def test_other_job_ignored(self, fixtures):
        library = fixtures['library']
        app = fixtures['app']

        # library@sha1 passes unit tests
        record_job_sha('library_unit', 1, 'owner', 'library', 'sha1')
        record_job_result('library_unit', 1, True, "passed")

        library_unit = fixtures['library_unit']
        app_unit = fixtures['app_unit']
        successful_job_shas = get_successful_job_shas({
            library_unit.id: {
                library.id: '',
            },
            app_unit.id: {
                app.id: '',
            },
        })
        assert successful_job_shas[library_unit.id] == {
            ('sha1',): 1,
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

        successful = get_successful_job_shas({
            app_integration.id: shas,
            app_integration2.id: shas,
        })
        assert successful == {
            app_integration.id: {
                ('sha2', 'sha3'): 1,
            },
            app_integration2.id: {
                ('sha4', 'sha5'): 1,
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
            get_successful_job_shas({app_integration_id: shas})
        assert qc.count == 1

        # 2 jobs
        with QueryCounter() as qc:
            get_successful_job_shas({
                app_integration_id: shas,
                app_unit_id: shas,
            })
        assert qc.count == 2

        # jobs with no projects
        with QueryCounter() as qc:
            get_successful_job_shas({
                app_integration_id: {},
                app_unit_id: {},
            })
        assert qc.count == 2


def build_check(session, project_name, sha):
    getattr(g, '_cache', {}).clear()
    pr = make_pr(session, project_name, sha)
    # project = session.query(Project).filter_by(name=project_name).one()
    # shas = {project_name: sha}
    return all(check.status for check in jenkins_check(pr))


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
    assert not build_check(session, 'library', lib_sha)

    # app@sha1 integration passes against library@lib_sha
    record_job_sha('app_integration', 1, 'owner', 'app', 'sha1')
    record_job_sha('app_integration', 1, 'owner', 'library', lib_sha)
    record_job_result('app_integration', 1, True, "passed")

    # library integration now satisfied
    assert build_check(session, 'library', lib_sha)


def test_check_no_jobs(session, app_context):
    project = Project(name='foo', owner='bar')
    session.add(project)
    session.commit()

    assert build_check(session, 'foo', 'sha')
