from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
control_engine = create_engine(settings.supabase_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=control_engine, class_=Session, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
