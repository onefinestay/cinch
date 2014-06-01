import pytest

from cinch.models import Project
from cinch.jenkins.models import Job


@pytest.fixture
def fixtures(session):
    """
    Dependency Graph:

    (library) <-[:DEPENDS_ON]- (app)

    Impact Graph:

    (library) -[:IMPACTS]-> (app)

    Test Suites:

    Unit: test a standalone project

        - library
        - app

    Integration: test a project against the things it depends upon

        - app: test app against library
    """

    # projects
    library = Project(name="library", owner='owner')
    app = Project(name="app", owner='owner')

    # unit jobs
    library_unit = Job(name="library_unit", projects=[library])
    app_unit = Job(name="app_unit", projects=[app])

    # integration jobs
    app_integration = Job(
        name="app_integration",
        projects=[app, library])

    session.add(library)
    session.add(app)

    session.add(library_unit)
    session.add(app_unit)

    session.add(app_integration)

    created = {obj.name: obj for obj in session.new}
    session.commit()

    return created
