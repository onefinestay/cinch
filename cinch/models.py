from flask.ext.sqlalchemy import SQLAlchemy

from cinch import app


STRING_LENGTH = 200


db = SQLAlchemy(app)


project_jobs = db.Table('project_jobs',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id')),
    db.Column('job_id', db.Integer, db.ForeignKey('job.id'))
)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(STRING_LENGTH))

    jobs = db.relationship('Job', secondary=project_jobs)


class JobType(db.Model):
    type = db.Column(db.String(STRING_LENGTH))


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jenkins_name = db.Column(db.String(STRING_LENGTH), unique=True)
    type_id = db.Column(db.String(STRING_LENGTH))

    projects = db.relationship('Project', secondary=project_jobs)


class PullRequest(db.Model):
    number = db.Column(db.Integer)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    head_commit = db.Column(db.String(40), db.ForeignKey('commit.sha'))
    ahead_of_master = db.Column(db.Integer, nullable=True)
    behind_master = db.Column(db.Integer, nullable=True)
    is_mergable = db.Column(db.Boolean, nullable=True)


class Commit(db.Model):
    sha = db.Column(db.String(40), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))


"""
class CodeReview():
    commit_sha
    reviewer
    status
"""

build_commits = db.Table('build_commits',
    db.Column('build_id', db.Integer, db.ForeignKey('build.id')),
    db.Column('commit_sha', db.Integer, db.ForeignKey('commit.sha'))
)


class Build(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jenkins_build_id = db.Column(db.Integer)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    result = db.Column(db.Boolean(nullable=True))

    commits = db.relationship('Commit', secondary=build_commits)



