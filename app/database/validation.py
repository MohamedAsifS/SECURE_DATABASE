from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

MUTATING_STATEMENTS = {
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Create,
    exp.Grant,
    exp.Revoke,
    exp.Command,
    exp.Merge,
}


@dataclass(frozen=True)
class QueryValidationResult:
    normalized_sql: str


class SQLReadOnlyValidator:
    @staticmethod
    def validate_read_only(sql: str) -> QueryValidationResult:
        parsed = sqlglot.parse_one(sql, read="postgres")

        read_only_roots = (
            exp.Select,
            exp.Union,
            exp.With,
            exp.Subquery,
            exp.Values,
            exp.Paren,
        )
        if not isinstance(parsed, read_only_roots):
            if isinstance(parsed, exp.Expression):
                if not any(isinstance(node, tuple(MUTATING_STATEMENTS)) for node in parsed.walk()):
                    if not isinstance(parsed, exp.Select):
                        raise ValueError("Only read-only SELECT queries are allowed")
            else:
                raise ValueError("Unable to parse SQL query")

        for node in parsed.walk():
            if isinstance(node, tuple(MUTATING_STATEMENTS)):
                raise ValueError("Mutating statements are not allowed")

        if parsed.find(exp.Select) is None:
            raise ValueError("Only SELECT statements are allowed")

        return QueryValidationResult(normalized_sql=parsed.sql(dialect="postgres"))
