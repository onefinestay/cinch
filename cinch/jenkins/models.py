from collections import OrderedDict

from cinch import db
from cinch.models import STRING_LENGTH


job_projects = db.Table(
    'job_projects',
    db.Column('job_id', db.Integer, db.ForeignKey('jobs.id'),
              primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'),
              primary_key=True),
)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(STRING_LENGTH), unique=True, nullable=False)
    projects = db.relationship('Project', secondary=job_projects)

    def __str__(self):
        return "{} {}".format(self.name, self.type_id)

    def ordered_projects(self):
        return sorted(list(self.projects), key=lambda p: p.name)


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

    def __str__(self):
        return "{}/{}".format(self.job.name, self.build_number)

    def project_commits(self):
        commits = OrderedDict()
        for project in self.job.ordered_projects():
            commits[project.name] = None

        for commit in self.commits:
            commits[commit.project.name] = commit.sha

        return commits

    def matches_pull_request(self, pull_request):
        return (pull_request.head in self.commits)
