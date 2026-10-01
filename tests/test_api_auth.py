from fastapi.testclient import TestClient

from app.auth.authentication import AuthenticatedUser
from app.main import app

client = TestClient(app)


def test_api_requires_authentication():
    response = client.get("/database")
    assert response.status_code == 401


def test_api_allows_authenticated_user(monkeypatch):
    async def fake_user():
        return AuthenticatedUser(user_id="user_1", scopes=set(), token_fingerprint="x")

    from app.api import database

    app.dependency_overrides[database.get_current_user] = fake_user

    response = client.get("/database")
    assert response.status_code in (404, 200)

    app.dependency_overrides.clear()
