from cinch import db
# db.engine.echo = True


STRING_LENGTH = 200


class Project(db.Model):
    __tablename__ = "projects"
    __table_args = (
        db.UniqueConstraint('owner', 'name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.String(STRING_LENGTH), nullable=False)
    name = db.Column(db.String(STRING_LENGTH), nullable=False)
    master_sha = db.Column(db.String(40), nullable=True)

    def web_url(self):
        return "https://github.com/{}/{}".format(self.owner, self.name)

    def __str__(self):
        return self.name


class PullRequest(db.Model):
    __tablename__ = "pull_requests"

    number = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'),
                           primary_key=True)
    head = db.Column(db.String(40), nullable=False)
    owner = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=False)
    ahead_of_master = db.Column(db.Integer, nullable=True)
    behind_master = db.Column(db.Integer, nullable=True)
    is_mergeable = db.Column(db.Boolean, nullable=True)
    is_open = db.Column(db.Boolean, nullable=True)

    project = db.relationship('Project', backref='pull_requests')


"""
class CodeReview():
    commit_sha
    reviewer
    status
"""

