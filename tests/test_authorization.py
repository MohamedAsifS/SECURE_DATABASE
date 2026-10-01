import pytest
from fastapi import HTTPException

from app.auth.authorization import SCOPE_DATA_READ, SCOPE_SCHEMA_READ, ScopeAuthorizer


def test_scope_authorization_allows_required_scope():
    ScopeAuthorizer.require_scope({SCOPE_SCHEMA_READ}, SCOPE_SCHEMA_READ)


def test_scope_authorization_denies_missing_scope():
    with pytest.raises(HTTPException):
        ScopeAuthorizer.require_scope({SCOPE_SCHEMA_READ}, SCOPE_DATA_READ)
