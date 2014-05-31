from __future__ import absolute_import

from collections import OrderedDict

from flask import url_for, g
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from cinch.check import check, CheckStatus
from cinch.models import db, Project, PullRequest
from .models import Job, Build, BuildSha
from .exceptions import UnknownProject, UnknownJob


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


def record_job_sha(job_name, build_number, project_owner, project_name, sha):
    """ The Jenkins notifications plugin provides no good way to include
    metadata generate during a build (e.g. resolved git refs) in the
    notification body. This enables an enpoint to collect such data _during_
    the build instead
    """

    session = db.session

    try:
        job = session.query(Job).filter(Job.name == job_name).one()
    except NoResultFound:
        raise UnknownJob(job_name)

    build = get_or_create_build(job, build_number)

    try:
        project = session.query(Project).filter(
            Project.owner==project_owner, Project.name==project_name
        ).one()
    except NoResultFound:
        raise UnknownProject(project_owner, project_name)

    build_sha = session.query(BuildSha).get((build.id, project.id))
    if build_sha is None:
        build_sha = BuildSha(build=build, project=project)
        session.add(build_sha)
    build_sha.sha = sha
    session.commit()


def record_job_result(job_name, build_number, success, status):
    """ Record status of a build. Shas should already have been provided to
    `record_job_sha` below.
    """

    try:
        job = db.session.query(Job).filter(Job.name == job_name).one()
    except NoResultFound:
        raise UnknownJob

    build = get_or_create_build(job, build_number)

    build.success = success
    build.status = status

    db.session.commit()


def get_job_master_shas():
    job_master_shas = {}
    for job in db.session.query(Job).options(joinedload('projects')):
        # The subqueries for the related projects are ordered in
        # `successful_job_shas` below. This order needs to match
        # the order use to look them up later for each pull_request.
        job_master_shas[job.id] = OrderedDict({
            project.id: project.master_sha
            for project in job.projects
        })
    return job_master_shas


def get_successful_job_shas(job_master_shas):
    # For each job, we construct a query that finds tuples of shas
    # for all successful builds. We can then match those against the required
    # shas for any given pull_request (the head for the project of the pr,
    # and master for any related projects). It may be possible to do this in
    # a single query, for for my sanity we're doing n queries for now. Note
    # that n depends on the number of _jobs_, not the number of builds or open
    # pull requests.

    session = db.session
    successful_job_shas = {}
    for job_id, shas in job_master_shas.items():
        # The subqueries for the related projects are ordered in
        # `successful_job_shas` below. This order needs to match
        # the order use to look them up later for each pull_request.
        base_query = session.query(
            Build.id, Build.build_number).filter_by(
            success=True).join(Job).filter_by(
            id=job_id).subquery(name='basequery')
        query = db.session.query(base_query)
        aliases = []

        for project_id in shas.keys():
            subquery_alias = session.query(
                BuildSha.build_id, BuildSha.sha
                ).filter(BuildSha.project_id == project_id
                ).subquery(name="project_{}_commits".format(project_id))
            aliases.append(subquery_alias)

            query = query.outerjoin(
                subquery_alias,
                subquery_alias.c.build_id == base_query.c.id,
            )

        columns = [base_query.c.build_number] + [
            alias.c.sha for alias in aliases]

        # for each job, successful_job_shas is a dictionary, mapping tuples
        # of shas (ordered as per the job_sha_map) for successful builds to
        # the build number in question
        successful_job_shas[job_id] = {
            result[1:]: result[0]
            for result in query.values(*columns)
        }

    return successful_job_shas


def get_successful_pr_builds(job_master_shas, successful_job_shas):
    pr_map = {}
    for pr in db.session.query(PullRequest
        ).filter_by(is_open=True
        ).options(
            joinedload('project')
    ):
        project = pr.project
        pr_job_map = {}

        for job in project.jobs:
            # take a copy of the master shas dict, and replace the shas for
            # this pull request's project by the pull request head
            job_id = job.id
            sha_dict = job_master_shas[job_id].copy()
            sha_dict[project.id] = pr.head
            shas = tuple(sha_dict.values())

            successful_shas = successful_job_shas[job_id]
            try:
                pr_job_map[job_id] = successful_shas[shas]
            except KeyError:
                pr_job_map[job_id] = None

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

    job_master_shas = get_job_master_shas()
    successful_job_shas = get_successful_job_shas(job_master_shas)

    return get_successful_pr_builds(job_master_shas, successful_job_shas)

@check
def jenkins_check(pull_request):
    pr_map = all_open_prs()

    job_ids = pr_map[pull_request].keys()
    if job_ids:
        jobs = db.session.query(Job).filter(Job.id.in_(job_ids))
    else:
        jobs = []

    # TODO: one url per job
    url = url_for(
        'jenkins.pull_request_status',
        project_owner=pull_request.project.owner,
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )

    check_statuses = []

    for job in sorted(jobs, key=lambda j: j.name):
        job_number = pr_map[pull_request][job.id]
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
