import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database.manager import DatabaseConnectionManager
from app.model.database import Base, DatabaseConnectionRecord


@pytest.fixture
def session():
    DatabaseConnectionManager._engine_cache.clear()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session)
    with maker() as db:
        yield db
    DatabaseConnectionManager._engine_cache.clear()


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


def test_get_connection_reuses_cached_engine(session, monkeypatch):
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

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    created = []

    def fake_create_engine(url, **kwargs):
        created.append(url)
        return FakeEngine()

    monkeypatch.setattr("app.database.manager.create_engine", fake_create_engine)

    manager = DatabaseConnectionManager(session)
    monkeypatch.setattr(manager.credential_provider, "retrieve", lambda _: "p@ss:word")

    first = manager.get_connection("user_a")
    second = manager.get_connection("user_a")

    assert first is second
    assert len(created) == 1


def test_delete_connection_disposes_cached_engine(session, monkeypatch):
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

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    fake_engine = FakeEngine()
    monkeypatch.setattr("app.database.manager.create_engine", lambda *args, **kwargs: fake_engine)

    manager = DatabaseConnectionManager(session)
    monkeypatch.setattr(manager.credential_provider, "retrieve", lambda _: "value")
    monkeypatch.setattr(manager.credential_provider, "delete", lambda _: None)
    _ = manager.get_connection("user_a")

    manager.delete_connection("user_a")
    assert fake_engine.disposed is True


def test_build_external_engine_uses_sqlalchemy_url(session, monkeypatch):
    session.add(
        DatabaseConnectionRecord(
            id="db_1",
            user_id="user_a",
            name="main",
            database_type="postgresql",
            host="db.example.com",
            port=5432,
            database_name="app",
            username="reader",
            credential_reference="DB_PASSWORD_test",
            ssl_required=True,
        )
    )
    session.commit()

    captured = {}

    class FakeEngine:
        def dispose(self):
            return None

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        return FakeEngine()

    monkeypatch.setattr("app.database.manager.create_engine", fake_create_engine)

    manager = DatabaseConnectionManager(session)
    monkeypatch.setattr(manager.credential_provider, "retrieve", lambda _: "p@ss:word/with?chars")
    _ = manager.get_connection("user_a")

    url = captured["url"]
    assert url.username == "reader"
    assert url.password == "p@ss:word/with?chars"
    assert url.host == "db.example.com"


def test_execute_query_enforces_size_limit_during_fetch(session, monkeypatch):
    settings = Settings(max_result_size_mb=1, max_query_rows=500, query_timeout_seconds=5)
    manager = DatabaseConnectionManager(session, settings=settings)

    class FakeResult:
        def __init__(self):
            self._calls = 0

        def keys(self):
            return ["payload"]

        def fetchmany(self, _size):
            self._calls += 1
            if self._calls == 1:
                return [("x" * 2_000_000,)]
            return []

    class FakeConnection:
        def execute(self, statement):
            if "SET statement_timeout" in str(statement):
                return None
            return FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(manager, "get_connection", lambda _: FakeEngine())

    with pytest.raises(ValueError, match="Result set too large"):
        manager.execute_query("user_a", "SELECT payload FROM table_name")
