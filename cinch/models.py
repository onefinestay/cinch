from cinch import db


STRING_LENGTH = 200

job_projects = db.Table(
    'job_projects',
    db.Column('job_id', db.Integer, db.ForeignKey('jobs.id'),
              primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'),
              primary_key=True),
)


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(STRING_LENGTH), unique=True, nullable=False)
    repo_name = db.Column(
        db.String(STRING_LENGTH), nullable=False, unique=True)
    master_sha = db.Column(db.String(40), nullable=True)

    jobs = db.relationship('Job', secondary=job_projects)


class JobType(db.Model):
    __tablename__ = "job_types"

    name = db.Column(db.String(STRING_LENGTH), primary_key=True)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(STRING_LENGTH), unique=True, nullable=False)
    type_id = db.Column(db.String(STRING_LENGTH),
                        db.ForeignKey('job_types.name'), nullable=False)

    job_type = db.relationship('JobType')
    projects = db.relationship('Project', secondary=job_projects)


class PullRequest(db.Model):
    __tablename__ = "pull_requests"

    number = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'),
                           primary_key=True)
    head_commit = db.Column(db.String(40), db.ForeignKey('commits.sha'),
                            nullable=False)
    owner = db.Column(db.Text, nullable=False)
    ahead_of_master = db.Column(db.Integer, nullable=True)
    behind_master = db.Column(db.Integer, nullable=True)
    is_mergable = db.Column(db.Boolean, nullable=True)

    head = db.relationship('Commit')
    project = db.relationship('Project')


class Commit(db.Model):
    __tablename__ = "commits"

    sha = db.Column(db.String(40), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'),
                           nullable=False)

    project = db.relationship('Project', foreign_keys=[project_id])

"""
class CodeReview():
    commit_sha
    reviewer
    status
"""

build_commits = db.Table(
    'build_commits',
    db.Column('build_id', db.Integer, db.ForeignKey('builds.id'),
              primary_key=True),
    db.Column('commit_sha', db.String(40), db.ForeignKey('commits.sha'),
              primary_key=True),
)


class Build(db.Model):
    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    build_number = db.Column(db.Integer)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'))
    success = db.Column(db.Boolean, nullable=True)
    status = db.Column(db.Text, nullable=True, default="")

    job = db.relationship('Job', backref='builds')
    commits = db.relationship(
        'Commit', secondary=build_commits, backref='builds')
