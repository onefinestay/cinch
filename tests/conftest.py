import os

import pytest


def pytest_addoption(parser):
    parser.addoption("--db-uri", action="store")


def pytest_configure(config):
    db_uri = config.getoption('db_uri')
    if db_uri:
        os.environ['CINCH_DB_URI'] = db_uri

    # disable error catching for better traceback
    from cinch import app
    app.testing = True


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


@pytest.yield_fixture(autouse=True)
def temp_config():
    from cinch import app
    original_config = app.config.copy()
    yield
    app.config = original_config
