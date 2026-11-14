from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def list_tables(engine: Engine) -> list[str]:
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query).fetchall()
    return [row[0] for row in rows]


def describe_table(engine: Engine, table_name: str) -> dict:
    columns_query = text(
        """
        SELECT
            c.column_name,
            c.data_type,
            c.is_nullable,
            EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = c.table_schema
                  AND tc.table_name = c.table_name
                  AND tc.constraint_type = 'PRIMARY KEY'
                  AND kcu.column_name = c.column_name
            ) AS is_primary_key
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.table_name = :table_name
        ORDER BY c.ordinal_position
        """
    )

    fk_query = text(
        """
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = :table_name
        ORDER BY kcu.column_name
        """
    )

    with engine.connect() as connection:
        columns = [
            dict(row._mapping)
            for row in connection.execute(columns_query, {"table_name": table_name})
        ]
        foreign_keys = [
            dict(row._mapping) for row in connection.execute(fk_query, {"table_name": table_name})
        ]

    return {"table_name": table_name, "columns": columns, "foreign_keys": foreign_keys}


def get_relationships(engine: Engine) -> list[dict]:
    query = text(
        """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY source_table, source_column
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query).fetchall()
    return [dict(row._mapping) for row in rows]
