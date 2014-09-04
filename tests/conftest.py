import os
import warnings

import pytest
import sqlalchemy.exc


def pytest_addoption(parser):
    parser.addoption("--db-uri", action="store")


def pytest_configure(config):
    db_uri = config.getoption('db_uri')
    if db_uri:
        os.environ['CINCH_DB_URI'] = db_uri

    # turn sqlalchemy warnings about empty `in_` clauses into errors
    warnings.simplefilter("error", category=sqlalchemy.exc.SAWarning)


@pytest.fixture
def session():
    # importing at the module level messes up coverage
    from cinch import db

    def drop_and_recreate_db():
        db.session.remove()  # make sure we start with a new session
        db.drop_all()
        db.create_all()

    drop_and_recreate_db()
    return db.session


@pytest.yield_fixture
def app_context():
    from cinch import app
    with app.test_request_context():
        yield app


@pytest.fixture(autouse=True)
def propagate_exceptions():
    from cinch import app
    app.config['PROPAGATE_EXCEPTIONS'] = True
