from cinch.models import db, Job, Project, Commit, Build


def record_job_result(job_name, build_number, shas, success, status):
    """
    e.g.
        shas = {
            'my_project': <sha>,
            'other_project': <sha>
        }
    """
    job = db.session.query(Job).filter(Job.name == job_name).one()

    # sanity check
    assert set([p.name for p in job.projects]) == set(shas.keys())

    build = Build(build_number=build_number, job=job, success=success, status=status)

    for project_name, sha in shas.items():
        project = db.session.query(Project).filter_by(name=project_name).one()
        commit = db.session.query(Commit).get(sha)
        if commit is None:
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
        # it should be possible to do this more efficiently with some
        # well written sql
    """

    # get all jobs relevant to this project and job type
    # (i.e. figure out the dependencies/impact)
    jobs = get_jobs(project_name, job_type)

    jobs_with_successful_builds = []

    # for each of the relevant jobs, find any build that matches the required
    # set of SHAs and also passed
    for job in jobs:

        # SHAs to match starts as the master_sha of the relevant projects
        job_shas = {
            project.name: project.master_sha
            for project in job.projects
        }
        shas = job_shas.copy()
        # but specific SHAs can be provided to test against
        shas.update(branch_shas)

        # iterate over all builds of this job. if one matches the exact set
        # of SHAs we're matching for, consider it a success
        for build in job.builds:
            commits = {
                commit.project.name: commit.sha
                for commit in build.commits
            }
            job_shas = {
                key: value for key, value in shas.items()
                if key in job_shas
            }
            if commits == job_shas and build.success:
                jobs_with_successful_builds.append(job.name)
                break

    return jobs_with_successful_builds


def test_check(project_name, project_sha, job_type):
    job_names = [job.name for job in get_jobs(project_name, job_type)]

    shas = {
        project_name: project_sha
    }
    successful_jobs = get_successful_builds(project_name, job_type, shas)

    return len(set(job_names) - set(successful_jobs)) == 0


def integration_test_check(project_name, project_sha):
    return test_check(project_name, project_sha, "integration")


def unit_test_check(project_name, project_sha):
    return test_check(project_name, project_sha, "unit")








