from flask import g

from cinch import app
from cinch.auth import requires_auth


from cinch.models import db, Job, Project, Commit, Build


def record_job_result(job_name, build_number, shas, result):
    """
    e.g.
        shas = {
            'my_project': <sha>,
            'other_project': <sha>
        }
    """

    job = db.session.query(Job).filter(Job.job_name == job_name).one()

    # sanity check
    assert set([p.name for p in job.projects]) == set(shas.keys())

    build = Build(build_number=build_number, job=job, result=result)

    for project_name, sha in shas.items():
        project = db.session.query(Project).filter_by(name=project_name).one()
        commit = Commit(sha=sha, project=project)
        build.commits.append(commit)

    db.session.add(build)
    db.session.commit()


@app.route('/')
def index():
    message = """
        <p>Hello World!<br>CI is a cinch!<br>
             <a href="/login/">login</a></br>
             <a href="/logout/">logout</a></br>
             <a href="/user">you</a></br>
             <a href="/secret/">secret</a>
        </p>"""

    return message


# test route
@app.route('/secret/')
@requires_auth
def test_auth():
    return 'you are special %s' % g.access_token
