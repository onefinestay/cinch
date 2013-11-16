from __future__ import absolute_import

from cinch.check import check
from cinch.models import db, Project, Commit
from .models import Job, Build


def get_or_create_build(job, build_number):
    """Return build by job and bubild_number. Create if missing

    Does not commit (assumes the user wants to make other changes
    to the session and will commit later)
    """
    build = db.session.query(Build).filter(
        Build.job == job,
        Build.build_number == build_number,
    ).first()

    if build is None:
        build = Build(job=job, build_number=build_number)
        db.session.add(build)

    return build


def record_job_sha(job_name, build_number, project_name, sha):
    """ The Jenkins notifications plugin provides no good way to include
    metadata generate during a build (e.g. resolved git refs) in the
    notification body. This enables an enpoint to collect such data _during_
    the build instead
    """

    job = db.session.query(Job).filter(Job.name == job_name).one()
    build = get_or_create_build(job, build_number)

    project = db.session.query(Project).filter_by(name=project_name).one()
    commit = db.session.query(Commit).get(sha)
    if commit is None:
        commit = Commit(sha=sha, project=project)
    build.commits.append(commit)

    db.session.commit()


def record_job_result(job_name, build_number, success, status):
    """ Record status of a build. Shas should already have been provided to
    `record_job_sha` below.
    """

    job = db.session.query(Job).filter(Job.name == job_name).one()
    build = get_or_create_build(job, build_number)

    build.success = success
    build.status = status

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


def build_check(project_name, project_sha, job_type):
    job_names = [job.name for job in get_jobs(project_name, job_type)]

    shas = {
        project_name: project_sha
    }
    successful_jobs = get_successful_builds(project_name, job_type, shas)

    return len(set(job_names) - set(successful_jobs)) == 0


def get_pull_request_status(pull_request, job_type):
    project = pull_request.project
    return build_check(project.name, pull_request.head_commit, job_type)


@check
def unit_check(pull_request):
    status = get_pull_request_status(pull_request, 'unit')
    return status, "Unit tests"


@check
def integration_check(pull_request):
    status = get_pull_request_status(pull_request, 'integration')
    return status, "Integration tests"
