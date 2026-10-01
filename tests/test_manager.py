import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import Base, DatabaseConnectionRecord
from app.database.manager import DatabaseConnectionManager


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session)
    with maker() as db:
        yield db


def test_get_connection_requires_owner_record(session):
    manager = DatabaseConnectionManager(session)
    with pytest.raises(PermissionError):
        manager._get_connection_record("user_a")


def test_get_connection_returns_users_own_record(session):
    session.add(
        DatabaseConnectionRecord(
            id="db_1",
            user_id="user_a",
            name="main",
            database_type="postgresql",
            host="localhost",
            port=5432,
            database_name="app",
            username="reader",
            credential_reference="DB_PASSWORD_test",
            ssl_required=True,
        )
    )
    session.commit()

    manager = DatabaseConnectionManager(session)
    record = manager._get_connection_record("user_a")
    assert record.user_id == "user_a"
