from __future__ import annotations

import logging
import time

from fastmcp import FastMCP

from app.auth.authorization import SCOPE_DATA_READ, SCOPE_SCHEMA_READ, ScopeAuthorizer
from app.database.connection import SessionLocal
from app.database.introspection import describe_table, get_relationships, list_tables
from app.database.manager import DatabaseConnectionManager

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool
    def list_tables_tool() -> dict:
        user_id = ScopeAuthorizer.require_mcp_scope(SCOPE_SCHEMA_READ)
        started = time.perf_counter()
        with SessionLocal() as session:
            manager = DatabaseConnectionManager(session)
            engine = manager.get_connection(user_id)
            tables = list_tables(engine)
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "tool=list_tables user_id=%s success=true execution_ms=%s rows=%s",
            user_id,
            elapsed,
            len(tables),
        )
        return {"tables": tables}

    @mcp.tool
    def describe_table_tool(table_name: str) -> dict:
        user_id = ScopeAuthorizer.require_mcp_scope(SCOPE_SCHEMA_READ)
        started = time.perf_counter()
        with SessionLocal() as session:
            manager = DatabaseConnectionManager(session)
            engine = manager.get_connection(user_id)
            table = describe_table(engine, table_name)
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info("tool=describe_table user_id=%s success=true execution_ms=%s", user_id, elapsed)
        return table

    @mcp.tool
    def get_relationships_tool() -> dict:
        user_id = ScopeAuthorizer.require_mcp_scope(SCOPE_SCHEMA_READ)
        started = time.perf_counter()
        with SessionLocal() as session:
            manager = DatabaseConnectionManager(session)
            engine = manager.get_connection(user_id)
            relationships = get_relationships(engine)
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "tool=get_relationships user_id=%s success=true execution_ms=%s rows=%s",
            user_id,
            elapsed,
            len(relationships),
        )
        return {"relationships": relationships}

    @mcp.tool
    def execute_read_query(sql: str) -> dict:
        user_id = ScopeAuthorizer.require_mcp_scope(SCOPE_DATA_READ)
        started = time.perf_counter()
        with SessionLocal() as session:
            manager = DatabaseConnectionManager(session)
            result = manager.execute_query(user_id, sql)
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "tool=execute_read_query user_id=%s success=true execution_ms=%s rows=%s",
            user_id,
            elapsed,
            result.row_count,
        )
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "total_execution_time_ms": elapsed,
        }
