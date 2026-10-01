from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.authentication import AuthenticatedUser, get_current_user
from app.database.connection import get_db_session
from app.database.manager import DatabaseConnectionManager

router = APIRouter(prefix="/database", tags=["database"])


class DatabaseCreateRequest(BaseModel):
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
    status: str


@router.post("", response_model=DatabaseMetadataResponse)
def create_or_update_database(
    request: DatabaseCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        manager.test_connection_payload(request.model_dump())
        record = manager.save_connection(user.user_id, request.model_dump())
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection failed",
        ) from error

    return DatabaseMetadataResponse(
        id=record.id,
        name=record.name,
        database_type=record.database_type,
        status="connected",
    )


@router.get("", response_model=DatabaseMetadataResponse)
def get_database(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        record = manager._get_connection_record(user.user_id)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database not configured",
        ) from error

    return DatabaseMetadataResponse(
        id=record.id,
        name=record.name,
        database_type=record.database_type,
        status="connected",
    )


@router.post("/test")
def test_database(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        manager.test_connection(user.user_id)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection test failed",
        ) from error
    return {"status": "connected"}


@router.delete("")
def delete_database(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    manager = DatabaseConnectionManager(session)
    try:
        manager.delete_connection(user.user_id)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database not configured",
        ) from error
    return {"status": "deleted"}
