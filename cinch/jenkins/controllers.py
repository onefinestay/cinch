from __future__ import absolute_import

from flask import url_for, g

from cinch.check import check, CheckStatus
from cinch.models import db, Project, Commit
from .models import Job, Build


def g_cache(func):
    """ For performance, we cache the results of certain queries that are
    repeated a large number of times (for the duration of the request only)
    """
    def wrapped(*args):
        try:
            cache = g._cache
        except AttributeError:
            cache = {}
            setattr(g, '_cache', cache)

        key = (func, tuple(args))
        if key not in cache:
            cache[key] = func(*args)
        return cache[key]

    return wrapped

@g_cache
def _get_job_names(project_name):
    return [job.name for job in get_jobs(project_name)]

@g_cache
def _get_jobs(project_name):
    from sqlalchemy.orm import subqueryload
    jobs = get_jobs(project_name
        ).options(subqueryload('projects')
        ).options(subqueryload('builds').subqueryload(Build.commits)
    )
    return jobs.all()


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


def get_jobs(project_name):

    return db.session.query(Job).join(Job.projects).filter(
            Project.name == project_name,
        )


def get_successful_builds(project_name, branch_shas):
    """
        Find successful jobs, given a project name and optional branch
        sha overrides for projects in the found jobs

        Finds all jobs related to the given project, and looks through all
        builds for that job, looking for builds that are
            1. successful
            2. match the head shas for the projects in that build (unless
                overriden with branch_shas)

        Arguments:
            project_name
                branch_shas: dict {project_name: sha}

        Return:
            A list of names of successful jobs
    """
    # it should be possible to do this more efficiently with some
    # well written sql

    # get all jobs relevant to this project and job type
    # (i.e. figure out the dependencies/impact)
    jobs = _get_jobs(project_name)

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


def build_check(project_name, project_sha):
    job_names = _get_job_names(project_name)

    shas = {
        project_name: project_sha
    }
    successful_jobs = get_successful_builds(project_name, shas)

    return len(set(job_names) - set(successful_jobs)) == 0


@check
def jenkins_check(pull_request):
    project = pull_request.project
    status = build_check(project.name, pull_request.head_commit)
    url = url_for(
        'jenkins.pull_request_status',
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )
    return CheckStatus(
        label="Jenkins",
        status=status,
        url=url,
    )