from __future__ import annotations

import logging

from fastapi import FastAPI
from fastmcp import FastMCP

from app.auth.authentication import get_authentication_service
from app.config import get_settings
from app.database.connection import control_engine
from app.model.database import Base
from app.mcp.tools import register_tools

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

Base.metadata.create_all(bind=control_engine)

auth_service = get_authentication_service()
mcp_server = FastMCP(
    name="Secure Database MCP",
    instructions="Read-only PostgreSQL tools with strict authentication and scope checks.",
    auth=auth_service.auth_provider,
)
register_tools(mcp_server)

app = FastAPI(title="Secure Database MCP")
app.mount("/mcp", mcp_server.http_app(path="/"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
