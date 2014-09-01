from cinch import db
from cinch.models import STRING_LENGTH, Project


class JobProject(db.Model):
    __tablename__ = 'job_projects'
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('projects.id'), primary_key=True)
    parameter_name = db.Column(db.String(STRING_LENGTH), nullable=True)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(STRING_LENGTH), unique=True, nullable=False)
    projects = db.relationship(
        'Project', secondary=JobProject.__table__, backref='jobs')

    def ordered_projects(self):
        return sorted(list(self.projects), key=lambda p: p.name)


class Build(db.Model):
    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    build_number = db.Column(db.Integer)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'))
    success = db.Column(db.Boolean, nullable=True)
    status = db.Column(db.Text, nullable=True, default="")

    job = db.relationship('Job')

    def __str__(self):
        return "{}/{}".format(self.job.name, self.build_number)


class BuildSha(db.Model):
    __tablename__ = "build_shas"

    build_id = db.Column(
        db.Integer, db.ForeignKey('builds.id'), primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('projects.id'), primary_key=True)
    sha = db.Column(db.String(40))

    build = db.relationship(Build)
    project = db.relationship(Project)
