from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class DatabaseConnectionRecord(Base):
    __tablename__ = "database_connections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    database_type: Mapped[str] = mapped_column(String(32), default="postgresql")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    database_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255))
    credential_reference: Mapped[str] = mapped_column(String(255), unique=True)
    ssl_required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class DatabaseCredentialRecord(Base):
    __tablename__ = "database_credentials"

    credential_reference: Mapped[str] = mapped_column(String(255), primary_key=True)
    encrypted_password: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


settings = get_settings()
control_engine = create_engine(settings.supabase_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=control_engine, class_=Session, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
