from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.authorization import SCOPE_DATA_READ
from app.auth.context import AuthenticatedUser
from app.auth.context import get_current_user
from app.database.connection import get_db_session
from app.database.manager import DatabaseConnectionManager
from app.main import app
from app.model.database import Base


client = TestClient(app)


def _connection_payload() -> dict:
    return {
        "name": "primary",
        "host": "db.example.com",
        "port": 5432,
        "database_name": "app",
        "username": "reader",
        "password": "password123",
        "ssl_required": True,
    }


def test_database_api_requires_authentication():
    response = client.get("/database")
    assert response.status_code == 401


def test_database_connection_workflow(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session)

    async def fake_current_user():
        return AuthenticatedUser(user_id="user_1", scopes={SCOPE_DATA_READ})

    def fake_get_db_session():
        with maker() as session:
            yield session

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db_session] = fake_get_db_session

    monkeypatch.setattr(DatabaseConnectionManager, "test_connection_payload", lambda self, payload: True)
    monkeypatch.setattr(DatabaseConnectionManager, "test_connection", lambda self, user_id: True)

    create_response = client.post("/database", json=_connection_payload())
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["name"] == "primary"
    assert "password" not in body

    get_response = client.get("/database")
    assert get_response.status_code == 200
    assert get_response.json()["database_name"] == "app"

    test_response = client.post("/database/test")
    assert test_response.status_code == 200

    delete_response = client.delete("/database")
    assert delete_response.status_code == 200

    get_after_delete = client.get("/database")
    assert get_after_delete.status_code == 404

    app.dependency_overrides.clear()


def test_database_register_requires_data_read_scope(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session)

    async def fake_current_user():
        return AuthenticatedUser(user_id="user_1", scopes=set())

    def fake_get_db_session():
        with maker() as session:
            yield session

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db_session] = fake_get_db_session

    monkeypatch.setattr(DatabaseConnectionManager, "test_connection_payload", lambda self, payload: True)

    response = client.post("/database", json=_connection_payload())
    assert response.status_code == 403

    app.dependency_overrides.clear()
