from sqlalchemy.orm.exc import NoResultFound

from .exceptions import UnknownProject
from .models import db, Project


def get_project(owner, name):
    session = db.session
    try:
        project = session.query(Project).filter(
            Project.owner == owner, Project.name == name
        ).one()
    except NoResultFound:
        raise UnknownProject(owner, name)

    return project
