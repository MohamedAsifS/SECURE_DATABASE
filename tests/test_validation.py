import pytest

from app.database.validation import SQLReadOnlyValidator


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users(id) VALUES (1)",
        "UPDATE users SET name='x'",
        "DELETE FROM users",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN x INT",
        "TRUNCATE TABLE users",
        "CREATE TABLE x(id INT)",
        "GRANT SELECT ON users TO test",
        "REVOKE SELECT ON users FROM test",
    ],
)
def test_mutating_queries_rejected(sql):
    with pytest.raises(ValueError):
        SQLReadOnlyValidator.validate_read_only(sql)


def test_select_allowed():
    result = SQLReadOnlyValidator.validate_read_only("SELECT id, name FROM users LIMIT 10")
    assert "SELECT" in result.normalized_sql
