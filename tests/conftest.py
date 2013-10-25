import pytest
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def clean_db(request):
    # importing at the module level messes up coverage
    from cinch import db

    def drop_and_recreate_db():
        db.drop_all()
        db.create_all()

    drop_and_recreate_db()


@pytest.fixture
def session(request, clean_db):
    from cinch import db
    return db.session
