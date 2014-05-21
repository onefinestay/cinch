from __future__ import absolute_import

from collections import OrderedDict

from flask import url_for, g
from sqlalchemy.orm import joinedload
# from sqlalchemy.sql.expression import and_

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


def has_successful_builds(job, branch_shas):
    """
        For a given job and main project, look for builds that are
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

    # SHAs to match starts as the master_sha of the relevant projects
    job_shas = {
        project.name: project.master_sha
        for project in job.projects
    }

    shas = job_shas.copy()
    # but specific SHAs can be provided to test against
    shas.update(branch_shas)

    # in case shas from unknown projects were provided, skip them
    shas = {
        key: value
        for key, value in shas.items()
        if key in job_shas
    }

    # iterate over all builds of this job. if one matches the exact set
    # of SHAs we're matching for, consider it a success
    for build in job.builds:
        if not build.success:
            continue

        commits = {
            commit.project.name: commit.sha
            for commit in build.commits
        }
        if commits == shas:
            return True

    return False


@g_cache
def all_open_prs():
    return _all_open_prs()

# so we can test without caching
def _all_open_prs():
    import time
    start = time.time()
    count = 0

    from cinch.models import PullRequest
    open_prs = db.session.query(PullRequest
        ).filter_by(is_open=True
        ).options(
            joinedload('project')
    ).all()

    db.session.query(Project).options(joinedload('jobs')).all()
    # projects = db.session.query(Project).options(joinedload('jobs')).all()

    # projects = db.session.query(Project).all()
    # jobs = db.session.query(Job).options(joinedload('projects')).all()
    # project_map = {project.name: project.id for project in projects}
    jobs = db.session.query(Job).options(joinedload('projects')).all()

    job_sha_map = {}
    for job in jobs:
        job_shas = OrderedDict({
            project.name: project.master_sha
            for project in job.projects
        })
        job_sha_map[job] = job_shas

    # interesting_shas = []


    # from .models import build_commits
    from .models import BuildCommits

    # successful_job_shas = {}
    successful_job_shas2 = {}
    for job, shas in job_sha_map.items():
        base_query = db.session.query(Build).filter_by(success=True)
        subquery = base_query.subquery(name='basequery')
        query = db.session.query(subquery)
        aliases = []
        # columns2 = [subquery.c.build_number]

        # build_query = db.session.query(Job).filter_by(id=job.id).join(Build).join(build_commits)

        for project_name, sha in shas.items():
            # alias = aliased(BuildCommits, name=project_name)
            build_query = db.session.query(BuildCommits).join(Build).join(Job).filter_by(id=job.id).subquery(name=project_name)
            # build_query = db.session.query(alias).join(Build).join(Job).filter_by(id=job.id).subquery(name=project_name)
            # columns2.append(build_query)
            aliases.append(build_query)
            # columns2.append(alias.commit_sha)


            # project_id = project_map[project_name]
            # alias = aliased(build_commits, name=project_name)
            # alias = alias(build_query)
            # aliases.append(alias)
            query = query.outerjoin(
                # alias,
                build_query,
            )

        # columns = [alias.c.commit_sha for alias in aliases]
        # successful_job_shas[job] = set(query.values(*columns))

        columns2 = [subquery.c.build_number] + [alias.c.commit_sha for alias in aliases]
        successful_job_shas2[job] = {result[1:]: result[0] for result in query.values(*columns2)}

        # if job.name == 'small_app_integration':
            # # import ipdb; ipdb.set_trace()
            # pass

        # if job.name == 'main_full':
            # import ipdb; ipdb.set_trace()



    pr_map = {}
    for pr in open_prs:
        project = pr.project
        pr_job_map = {}

        for job in project.jobs:
            sha_map = job_sha_map[job].copy()
            sha_map[project.name] = pr.head_commit
            # pr_job_map[job] = sha_map
            # interesting_shas.extend(sha_map.values())
            count += 1
            shas = tuple(sha_map.values())

            # if job.name == 'main_static_analysis' and pr.number == 1194:
                # import ipdb; ipdb.set_trace()

            # pr_job_map[job] = (shas in successful_job_shas[job])
            successful_shas = successful_job_shas2[job]
            try:
                pr_job_map[job] = successful_shas[shas]
            except KeyError:
                pr_job_map[job] = None

            # if shas in successful_job_shas[job]:
                # import ipdb; ipdb.set_trace()

        pr_map[pr] = pr_job_map

    # import ipdb; ipdb.set_trace()
    print count
    print time.time() - start
    return pr_map


@check
def jenkins_check(pull_request):
    pr_map = all_open_prs()

    # project = pull_request.project

    # get all jobs relevant to this project and job type
    # (i.e. figure out the dependencies/impact)
    # jobs = _get_jobs(project.name)
    jobs = pr_map[pull_request].keys()

    # shas = {
        # project.name: pull_request.head_commit,
    # }
    # todo: one url per job
    url = url_for(
        'jenkins.pull_request_status',
        project_name=pull_request.project.name,
        pr_number=pull_request.number,
    )

    check_statuses = []

    # for each of the relevant jobs, find any build that matches the required
    # set of SHAs and also passed
    for job in sorted(jobs, key=lambda j: j.name):
        # status = False # has_successful_builds(job, shas)
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
