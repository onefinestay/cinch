from __future__ import absolute_import

from collections import OrderedDict, namedtuple

from flask import url_for, g
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.orm.exc import NoResultFound

from cinch import app
from cinch.check import check, CheckStatus
from cinch.models import db, Project, PullRequest
from cinch.worker import dispatcher, PullRequestStatusUpdated
from .models import Job, Build, BuildSha
from .exceptions import UnknownProject, UnknownJob


# for pep8
NULL = None


BuildInfo = namedtuple('BuildInfo', ['build_number', 'status'])


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


def clear_g_cache():
    """Test helper to clear the `g_cache`"""
    getattr(g, '_cache', {}).clear()


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


def handle_build_updated(build):
    """ This will dispatch events for are all the prs that *might* be affected
    by a change in status of this build. If this build is not for a pull
    request against master shas in each of the other projects, the worker will
    determine the status has not changed.
    """

    # we need to see if any of the shas associated with this build match any
    # open pull requests
    session = db.session

    build_shas = session.query(BuildSha.sha).filter_by(build=build).all()
    build_shas = [build_sha.sha for build_sha in build_shas]

    pulls = session.query(PullRequest).filter(
        PullRequest.is_open == True,
        or_(
            PullRequest.head.in_(build_shas),
            PullRequest.merge_head.in_(build_shas)
        ),
    )

    with dispatcher() as dispatch:
        for pull in pulls:
            event = PullRequestStatusUpdated(data={
                'pull_request': (pull.number, pull.project_id),
            })
            dispatch(event)


def record_job_sha(job_name, build_number, project_owner, project_name, sha):
    """ The Jenkins notifications plugin provides no good way to include
    metadata generate during a build (e.g. resolved git refs) in the
    notification body. This enables an endpoint to collect such data _during_
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
            Project.owner == project_owner, Project.name == project_name
        ).one()
    except NoResultFound:
        raise UnknownProject(project_owner, project_name)

    build_sha = session.query(BuildSha).get((build.id, project.id))
    if build_sha is None:
        build_sha = BuildSha(build=build, project=project)
        session.add(build_sha)
    build_sha.sha = sha
    session.commit()

    handle_build_updated(build)


def record_job_result(job_name, build_number, success, status):
    """ Record status of a build. Shas should already have been provided to
    `record_job_sha` below.
    """

    try:
        job = db.session.query(Job).filter(Job.name == job_name).one()
    except NoResultFound:
        raise UnknownJob(job_name)

    build = get_or_create_build(job, build_number)

    build.success = success
    build.status = status
    db.session.commit()

    handle_build_updated(build)


def get_job_master_shas():
    job_master_shas = {}
    for job in db.session.query(Job).options(joinedload('projects')):
        # The BuildSha aliases for the related projects are ordered in
        # `get_job_sha_statuses` below. This order needs to match
        # the order use to look them up later for each pull_request.
        job_master_shas[job.id] = OrderedDict({
            project.id: project.master_sha
            for project in job.projects
        })
    return job_master_shas


def get_job_build_query(job_id, project_ids):
    """Construct a query, and column aliases for querying sha tuples for builds
    of a given job

    :Parameters:
        job_id
        project_ids

    :Returns:
        query, base_alias, project_sha_columns

        The aliases for the projects are ordered to match the order of
        `project_ids`
    """
    session = db.session
    query = session.query(Build.id, Build.build_number, Build.success
        ).join(Job).filter(Job.id == job_id)
    aliases = []

    for project_id in project_ids:
        build_sha_alias = aliased(
            BuildSha, name="project_{}_commits".format(project_id))
        aliases.append(build_sha_alias)

        query = query.outerjoin(
            build_sha_alias,
            and_(
                build_sha_alias.build_id == Build.id,
                build_sha_alias.project_id == project_id,
            )
        )

    sha_columns = [alias.sha for alias in aliases]
    query = query.filter(and_(column != NULL for column in sha_columns))

    return query, sha_columns


def get_job_sha_statuses(job_master_shas):
    # For each job, we construct a query that finds tuples of shas for all
    # known builds. We can then match those against the required shas for any
    # given pull_request (the head for the project of the pr, and master for
    # any related projects). It may be possible to do this in a single query,
    # for for my sanity we're doing n queries for now. Note that n depends on
    # the number of _jobs_, not the number of builds or open pull requests.

    job_statuses = {}
    for job_id, shas in job_master_shas.items():
        # The subqueries for the related projects are ordered in
        # `successful_job_shas` below. This order needs to match
        # the order use to look them up later for each pull_request.
        query, sha_columns = get_job_build_query(
            job_id, shas.keys())

        # for each job, successful_job_shas is a dictionary, mapping tuples
        # of shas (ordered as per the job_sha_map) for successful builds to
        # the build number in question
        job_statuses[job_id] = {}
        results = query.values(Build.build_number, Build.success, *sha_columns)
        for result in results:
            shas = result[2:]
            job_statuses[job_id][shas] = BuildInfo(
                result.build_number, result.success)

    return job_statuses


def get_pr_builds(job_master_shas, job_sha_map):
    pr_map = {}
    pull_requests = db.session.query(
        PullRequest
        ).filter(
            PullRequest.is_open == True
        ).options(
            joinedload('project')
    )
    for pr in pull_requests:
        project = pr.project
        pr_job_map = {}

        for job in project.jobs:
            # Take a copy of the master shas dict, and replace the shas for
            # this pull request's project by the pull request head. we check
            # for both the head and the merge_head, accepting preferring
            # results from the merge head.
            job_id = job.id
            head_sha_dict = job_master_shas[job_id].copy()
            head_sha_dict[project.id] = pr.head
            head_shas = tuple(head_sha_dict.values())
            merge_head_sha_dict = job_master_shas[job_id].copy()
            merge_head_sha_dict[project.id] = pr.merge_head
            merge_head_shas = tuple(merge_head_sha_dict.values())

            job_shas = job_sha_map[job_id]
            missing = (None, None)
            head_build_number, head_status = job_shas.get(head_shas, missing)
            merge_head_build_number, merge_head_status = job_shas.get(
                merge_head_shas, missing)

            # let results for merge head overwrite results for head. fall back
            # to head (which may be None)
            if merge_head_build_number is not None:
                build_number = merge_head_build_number
                status = merge_head_status
            else:
                build_number = head_build_number
                status = head_status

            pr_job_map[job_id] = BuildInfo(build_number, status)

        pr_map[pr] = pr_job_map

    return pr_map


@g_cache
def all_open_prs():
    job_master_shas = get_job_master_shas()
    job_shas = get_job_sha_statuses(job_master_shas)

    return get_pr_builds(job_master_shas, job_shas)


@check
def jenkins_check(pull_request):
    pr_map = all_open_prs()

    job_ids = pr_map[pull_request].keys()
    if job_ids:
        jobs = db.session.query(Job).filter(Job.id.in_(job_ids))
    else:
        jobs = []

    # TODO: one url per job
    pull_request_status_url = url_for(
        'jenkins.pull_request_status',
        project_owner=pull_request.project.owner,
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )

    check_statuses = []
    jenkins_url = app.config.get('JENKINS_URL', 'http://jenkins.example.com')

    for job in sorted(jobs, key=lambda j: j.name):
        build_number, status = pr_map[pull_request][job.id]

        if build_number is None:
            status = None
            label = "Jenkins: {}".format(job.name)
            url = pull_request_status_url
        else:
            label = "Jenkins: {}: {}".format(job.name, build_number)
            url = "{}/job/{}/{}/".format(jenkins_url, job.name, build_number)

        check_statuses.append(
            CheckStatus(
                label=label,
                status=status,
                url=url,
            )
        )

    return check_statuses
