from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.credentials.provider import EnvironmentCredentialProvider
from app.database.validation import SQLReadOnlyValidator
from app.model.database import DatabaseConnectionRecord, DatabaseCredentialRecord


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    execution_time_ms: int


@dataclass(frozen=True)
class CachedEngine:
    fingerprint: tuple[str, int, str, str, str, bool]
    engine: Engine


class DatabaseConnectionManager:
    _engine_cache: dict[str, CachedEngine] = {}
    _engine_cache_lock = Lock()

    def __init__(self, session: Session, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.credential_provider = EnvironmentCredentialProvider(
            self.settings.credential_encryption_key
        )

    @staticmethod
    def _build_fingerprint(
        record: DatabaseConnectionRecord,
    ) -> tuple[str, int, str, str, str, bool]:
        return (
            record.host,
            record.port,
            record.database_name,
            record.username,
            record.credential_reference,
            record.ssl_required,
        )

    @classmethod
    def _dispose_cached_engine(cls, user_id: str) -> None:
        with cls._engine_cache_lock:
            cached = cls._engine_cache.pop(user_id, None)
        if cached is not None:
            cached.engine.dispose()

    @classmethod
    def dispose_all_cached_engines(cls) -> None:
        with cls._engine_cache_lock:
            cached_engines = list(cls._engine_cache.values())
            cls._engine_cache.clear()
        for cached in cached_engines:
            cached.engine.dispose()

    @classmethod
    def _get_cached_engine(
        cls, user_id: str, fingerprint: tuple[str, int, str, str, str, bool]
    ) -> Engine | None:
        with cls._engine_cache_lock:
            cached = cls._engine_cache.get(user_id)
            if cached is None:
                return None
            if cached.fingerprint == fingerprint:
                return cached.engine
        cls._dispose_cached_engine(user_id)
        return None

    @classmethod
    def _cache_engine(
        cls,
        user_id: str,
        fingerprint: tuple[str, int, str, str, str, bool],
        engine: Engine,
    ) -> None:
        with cls._engine_cache_lock:
            previous = cls._engine_cache.get(user_id)
            cls._engine_cache[user_id] = CachedEngine(fingerprint=fingerprint, engine=engine)
        if previous is not None and previous.engine is not engine:
            previous.engine.dispose()

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
        encrypted = self.credential_provider.store(credential_reference, password)
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
        credential_value = self.credential_provider.retrieve(record.credential_reference)
        ssl_mode = "require" if record.ssl_required else "prefer"
        url = URL.create(
            **{
                "drivername": "postgresql+psycopg",
                "username": record.username,
                "password": credential_value,
                "host": record.host,
                "port": record.port,
                "database": record.database_name,
                "query": {"sslmode": ssl_mode},
            }
        )
        return create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.settings.query_timeout_seconds},
        )

    def get_connection(self, user_id: str) -> Engine:
        record = self._get_connection_record(user_id)
        fingerprint = self._build_fingerprint(record)
        cached_engine = self._get_cached_engine(user_id, fingerprint)
        if cached_engine is not None:
            return cached_engine
        engine = self._build_external_engine(record)
        self._cache_engine(user_id, fingerprint, engine)
        return engine

    def test_connection(self, user_id: str) -> bool:
        engine = self.get_connection(user_id)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def test_connection_payload(self, payload: dict) -> bool:
        ssl_mode = "require" if payload.get("ssl_required", True) else "prefer"
        credential_value = payload["password"]
        url = URL.create(
            **{
                "drivername": "postgresql+psycopg",
                "username": payload["username"],
                "password": credential_value,
                "host": payload["host"],
                "port": payload["port"],
                "database": payload["database_name"],
                "query": {"sslmode": ssl_mode},
            }
        )
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.settings.query_timeout_seconds},
        )
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
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
        self._dispose_cached_engine(user_id)
        return existing

    def delete_connection(self, user_id: str) -> None:
        record = self._get_connection_record(user_id)
        self._dispose_cached_engine(user_id)
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
            with engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(
                    text(
                        "SET LOCAL statement_timeout = "
                        f"{self.settings.query_timeout_seconds * 1000}"
                    )
                )
                result = connection.execute(text(limited_sql))
                columns = list(result.keys())

                max_size_bytes = self.settings.max_result_size_mb * 1024 * 1024
                running_size_bytes = len(
                    json.dumps({"columns": columns, "rows": []}, default=str).encode("utf-8")
                )
                rows: list[list] = []
                batch_size = min(100, self.settings.max_query_rows)
                while len(rows) < self.settings.max_query_rows:
                    batch = result.fetchmany(batch_size)
                    if not batch:
                        break

                    for row in batch:
                        serialized_row = list(row)
                        row_size = len(json.dumps(serialized_row, default=str).encode("utf-8"))
                        if running_size_bytes + row_size > max_size_bytes:
                            raise ValueError("Result set too large")
                        running_size_bytes += row_size
                        rows.append(serialized_row)
                        if len(rows) >= self.settings.max_query_rows:
                            break
        except SQLAlchemyError as error:
            raise ValueError("Database query failed") from error

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
        )
