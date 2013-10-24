from cinch import app

from cinch.models import db, Job, Project, Commit, Build


@app.route('/')
def index():
    return 'Hello World!'


def record_job_result(jenkins_name, jenkins_build_id, shas, result):
    """
    e.g.
        shas = {
            'my_project': <sha>,
            'other_project': <sha>
        }
    """

    job = db.session.query(Job).filter(Job.jenkins_name == jenkins_name).one()

    # sanity check
    assert set([p.name for p in job.projects]) == set(shas.keys())

    build = Build(jenkins_build_id=jenkins_build_id, job=job, result=result)

    for project_name, sha in shas.items():
        project = db.session.query(Project).filter_by(name=project_name).one()
        commit = Commit(sha=sha, project=project)
        build.commits.append(commit)

    db.session.add(build)
    db.session.commit()
