from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.credentials.provider import EnvironmentCredentialProvider
from app.database.connection import DatabaseConnectionRecord, DatabaseCredentialRecord
from app.database.validation import SQLReadOnlyValidator


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    execution_time_ms: int


class DatabaseConnectionManager:
    def __init__(self, session: Session, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.credential_provider = EnvironmentCredentialProvider(
            self.settings.credential_encryption_key
        )

    def _get_connection_record(self, user_id: str) -> DatabaseConnectionRecord:
        record = (
            self.session.query(DatabaseConnectionRecord)
            .filter(DatabaseConnectionRecord.user_id == user_id)
            .one_or_none()
        )
        if record is None:
            raise PermissionError("No database connection configured for user")
        return record

    def _store_credential(self, credential_reference: str, password: str) -> None:
        self.credential_provider.store(credential_reference, password)
        encrypted = self.credential_provider.retrieve(credential_reference)
        row = self.session.get(DatabaseCredentialRecord, credential_reference)
        if row is None:
            row = DatabaseCredentialRecord(
                credential_reference=credential_reference,
                encrypted_password=encrypted,
            )
            self.session.add(row)
        else:
            row.encrypted_password = encrypted

    def _build_external_engine(self, record: DatabaseConnectionRecord) -> Engine:
        password = self.credential_provider.retrieve(record.credential_reference)
        ssl_mode = "require" if record.ssl_required else "prefer"
        url = (
            f"postgresql+psycopg://{record.username}:{password}@{record.host}:{record.port}/"
            f"{record.database_name}?sslmode={ssl_mode}"
        )
        return create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.settings.query_timeout_seconds},
        )

    def get_connection(self, user_id: str) -> Engine:
        record = self._get_connection_record(user_id)
        return self._build_external_engine(record)

    def test_connection(self, user_id: str) -> bool:
        engine = self.get_connection(user_id)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def test_connection_payload(self, payload: dict) -> bool:
        ssl_mode = "require" if payload.get("ssl_required", True) else "prefer"
        password = payload["password"]
        url = (
            f"postgresql+psycopg://{payload['username']}:{password}@{payload['host']}:{payload['port']}/"
            f"{payload['database_name']}?sslmode={ssl_mode}"
        )
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.settings.query_timeout_seconds},
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def save_connection(self, user_id: str, payload: dict) -> DatabaseConnectionRecord:
        existing = (
            self.session.query(DatabaseConnectionRecord)
            .filter(DatabaseConnectionRecord.user_id == user_id)
            .one_or_none()
        )
        connection_id = existing.id if existing else f"db_{uuid.uuid4().hex[:16]}"
        credential_reference = (
            existing.credential_reference if existing else f"DB_PASSWORD_{uuid.uuid4().hex[:16]}"
        )

        self._store_credential(credential_reference, payload["password"])

        if existing is None:
            existing = DatabaseConnectionRecord(
                id=connection_id,
                user_id=user_id,
                name=payload["name"],
                database_type="postgresql",
                host=payload["host"],
                port=payload["port"],
                database_name=payload["database_name"],
                username=payload["username"],
                credential_reference=credential_reference,
                ssl_required=payload.get("ssl_required", True),
            )
            self.session.add(existing)
        else:
            existing.name = payload["name"]
            existing.host = payload["host"]
            existing.port = payload["port"]
            existing.database_name = payload["database_name"]
            existing.username = payload["username"]
            existing.ssl_required = payload.get("ssl_required", True)

        self.session.commit()
        self.session.refresh(existing)
        return existing

    def delete_connection(self, user_id: str) -> None:
        record = self._get_connection_record(user_id)
        self.credential_provider.delete(record.credential_reference)
        self.session.query(DatabaseCredentialRecord).filter(
            DatabaseCredentialRecord.credential_reference == record.credential_reference
        ).delete()
        self.session.delete(record)
        self.session.commit()

    def execute_query(self, user_id: str, sql: str) -> QueryResult:
        validated = SQLReadOnlyValidator.validate_read_only(sql)
        limited_sql = (
            "SELECT * FROM "
            f"({validated.normalized_sql}) AS mcp_read_query "
            f"LIMIT {self.settings.max_query_rows}"
        )

        started = time.perf_counter()
        engine = self.get_connection(user_id)
        try:
            with engine.connect() as connection:
                connection.execute(
                    text(f"SET statement_timeout = {self.settings.query_timeout_seconds * 1000}")
                )
                result = connection.execute(text(limited_sql))
                rows = result.fetchall()
                columns = list(result.keys())
        except SQLAlchemyError as error:
            raise ValueError("Database query failed") from error

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        safe_rows = [list(row) for row in rows]

        response_size_bytes = len(str({"columns": columns, "rows": safe_rows}).encode("utf-8"))
        if response_size_bytes > self.settings.max_result_size_mb * 1024 * 1024:
            raise ValueError("Result set too large")

        return QueryResult(
            columns=columns,
            rows=safe_rows,
            row_count=len(safe_rows),
            execution_time_ms=elapsed_ms,
        )
