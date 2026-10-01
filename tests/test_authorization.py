import pytest
from fastapi import HTTPException

from app.auth.authentication import AuthenticatedUser
from app.auth.authorization import SCOPE_DATA_READ, SCOPE_SCHEMA_READ, ScopeAuthorizer


def test_scope_authorization_allows_required_scope():
    user = AuthenticatedUser(user_id="user_1", scopes={SCOPE_SCHEMA_READ}, token_fingerprint="x")
    ScopeAuthorizer.require_scope(user, SCOPE_SCHEMA_READ)


def test_scope_authorization_denies_missing_scope():
    user = AuthenticatedUser(user_id="user_1", scopes={SCOPE_SCHEMA_READ}, token_fingerprint="x")
    with pytest.raises(HTTPException):
        ScopeAuthorizer.require_scope(user, SCOPE_DATA_READ)
