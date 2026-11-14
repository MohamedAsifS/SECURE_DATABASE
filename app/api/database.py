from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.context import AuthenticatedUser, get_current_user
from app.auth.authorization import SCOPE_DATA_READ, ScopeAuthorizer
from app.database.connection import get_db_session
from app.database.manager import DatabaseConnectionManager

router = APIRouter(prefix="/database", tags=["database"])


class DatabaseConnectionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)
    ssl_required: bool = True


class DatabaseMetadataResponse(BaseModel):
    id: str
    name: str
    database_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_required: bool
    status: str


def _to_safe_metadata(record) -> DatabaseMetadataResponse:
    return DatabaseMetadataResponse(
        id=record.id,
        name=record.name,
        database_type=record.database_type,
        host=record.host,
        port=record.port,
        database_name=record.database_name,
        username=record.username,
        ssl_required=record.ssl_required,
        status="connected",
    )


@router.post("", response_model=DatabaseMetadataResponse)
def register_or_update_database(
    payload: DatabaseConnectionPayload,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    # Only data-read users can register connections for query tools.
    ScopeAuthorizer.require_scope(user.scopes, SCOPE_DATA_READ)

    manager = DatabaseConnectionManager(session)
    try:
        manager.test_connection_payload(payload.model_dump())
        record = manager.save_connection(user.user_id, payload.model_dump())
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to validate and save database connection",
        ) from error

    return _to_safe_metadata(record)


@router.get("", response_model=DatabaseMetadataResponse)
def get_database_connection(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        record = manager._get_connection_record(user.user_id)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found",
        ) from error

    return _to_safe_metadata(record)


@router.post("/test")
def test_database_connection(
    payload: DatabaseConnectionPayload | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)

    try:
        if payload is None:
            manager.test_connection(user.user_id)
        else:
            ScopeAuthorizer.require_scope(user.scopes, SCOPE_DATA_READ)
            manager.test_connection_payload(payload.model_dump())
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection test failed",
        ) from error

    return {"status": "ok"}


@router.delete("")
def delete_database_connection(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        manager.delete_connection(user.user_id)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found",
        ) from error

    return {"status": "deleted"}
