from __future__ import absolute_import

from collections import OrderedDict

from flask import url_for, g
from sqlalchemy.orm import joinedload

from cinch.check import check, CheckStatus
from cinch.models import db, Project, Commit, PullRequest
from .models import Job, Build, build_commits


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


def get_job_shas():
    job_shas = {}
    for job in db.session.query(Job).options(joinedload('projects')):
        # The subqueries for the related projects are ordered in
        # `successful_job_shas` below. This order needs to match
        # the order use to look them up later for each pull_request.
        job_shas[job] = OrderedDict({
            project.name: project.master_sha
            for project in job.projects
        })
    return job_shas


def get_successful_job_shas(job_shas):
    # For each job, we construct a query that finds tuples of shas
    # for all successful builds. We can then match those against the required
    # shas for any given pull_request (the head for the project of the pr,
    # and master for any related projects). It may be possible to do this in
    # a single query, for for my sanity we're doing n queries for now. Note
    # that n depends on the number of _jobs_, not the number of open
    # pull requests.
    successful_job_shas = {}
    for job, shas in job_shas.items():
        # The subqueries for the related projects are ordered in
        # `successful_job_shas` below. This order needs to match
        # the order use to look them up later for each pull_request.
        base_query = db.session.query(Build).filter_by(
            success=True).subquery(name='basequery')
        query = db.session.query(base_query)
        aliases = []

        for project_name in shas:
            subquery_alias = db.session.query(
                build_commits
                ).join(Build).join(Job).filter_by(
                id=job.id
                ).subquery(name=project_name)
            aliases.append(subquery_alias)

            query = query.outerjoin(
                subquery_alias,
            )

        columns = [base_query.c.build_number] + [
            alias.c.commit_sha for alias in aliases]

        # for each job, successful_job_shas is a dictionary, mapping tuples
        # of shas (ordered as per the job_sha_map) for successful builds to
        # the build number in question
        successful_job_shas[job] = {
            result[1:]: result[0]
            for result in query.values(*columns)
        }

    return successful_job_shas


def get_successful_pr_builds(job_shas, successful_job_shas):
    pr_map = {}
    for pr in db.session.query(PullRequest
        ).filter_by(is_open=True
        ).options(
            joinedload('project')
    ):
        project = pr.project
        pr_job_map = {}

        for job in project.jobs:
            sha_map = job_shas[job].copy()
            sha_map[project.name] = pr.head_commit
            shas = tuple(sha_map.values())

            successful_shas = successful_job_shas[job]
            try:
                pr_job_map[job] = successful_shas[shas]
            except KeyError:
                pr_job_map[job] = None

        pr_map[pr] = pr_job_map

    return pr_map


@g_cache
def all_open_prs():
    return _all_open_prs()

# so we can test without caching
def _all_open_prs():
    """
        TODO: update

        For a given job and main project, look for builds that are
            1. successful
            2. match the head shas for the projects in that build (unless
                overriden with branch_shas)

    """

    job_shas = get_job_shas()
    successful_job_shas = get_successful_job_shas(job_shas)

    return get_successful_pr_builds(job_shas, successful_job_shas)

@check
def jenkins_check(pull_request):
    pr_map = all_open_prs()

    jobs = pr_map[pull_request].keys()

    # TODO: one url per job
    url = url_for(
        'jenkins.pull_request_status',
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )

    check_statuses = []

    for job in sorted(jobs, key=lambda j: j.name):
        job_number = pr_map[pull_request][job]
        status = job_number is not None
        label = "Jenkins: {} [{}]".format(job.name, job_number)
        check_statuses.append(
            CheckStatus(
                label=label,
                status=status,
                url=url,
            )
        )

    return check_statuses
