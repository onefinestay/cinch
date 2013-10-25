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


def get_jobs(project_name, job_type):

    return db.session.query(Job).join(Job.projects).filter(
        Project.name == project_name,
        Job.type_id == job_type)


def get_successful_builds(project_name, job_type, branch_shas):
    """

        branch_shas= {
            library: my_branch,
        }
    """

    jobs = get_jobs(project_name, job_type)


    jobs_with_successful_builds = []


    for job in jobs:
        # it should be possible to do this more efficiently with some
        # well written sql

        shas = {
            project.name: project.master_sha
            for project in job.projects
        }
        shas.update(branch_shas)

        for build in job.builds:
            commits = {
                commit.project.name: commit.sha
                for commit in build.commits
            }

            if commits == shas and build.result:
                jobs_with_successful_builds.append(job.name)
                break

    return jobs_with_successful_builds
