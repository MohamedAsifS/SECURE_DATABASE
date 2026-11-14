# SECURE_DATABASE

Production-minded V1 read-only Database MCP Server built with Python, FastMCP, FastAPI, and PostgreSQL.

## Features (V1)

- Authentication via FastMCP JWT verifier
- Scope-based authorization (`database:schema:read`, `database:data:read`)
- One external PostgreSQL connection per user
- Secure credential abstraction (`CredentialProvider`)
- Schema discovery tools:
  - `list_tables`
  - `describe_table`
  - `get_relationships`
- Read-only query tool:
  - `execute_read_query`
- Secure connection workflow API:
  - `POST /database` (register/update + connectivity check)
  - `GET /database` (safe metadata only)
  - `POST /database/test` (test saved or provided config)
  - `DELETE /database`
- Query guardrails:
  - `MAX_QUERY_ROWS`
  - `QUERY_TIMEOUT_SECONDS`
  - `MAX_RESULT_SIZE_MB`
- SQLAlchemy models organized in `app/model`

## Security Notes

- Credentials are never returned by MCP tools.
- Passwords are handled through a credential reference abstraction.
- SQL write/admin operations are blocked by SQL parsing validation.
- SQL execution runs inside PostgreSQL read-only transactions.
- Use a read-only PostgreSQL user (for example: `ai_readonly`) with only `SELECT` permissions.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn app.main:app --reload
```

## Docker

```bash
docker compose up --build
```

## Tests

```bash
pytest
```

## Environment

See `.env.example`.
