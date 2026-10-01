from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastmcp.server.auth import JWTVerifier, RemoteAuthProvider

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    scopes: set[str]
    token_fingerprint: str


class AuthenticationService:
    def __init__(self, settings: Settings):
        jwks_uri = f"{settings.auth_issuer.rstrip('/')}/.well-known/jwks.json"
        self.verifier = JWTVerifier(
            jwks_uri=jwks_uri,
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
        )
        self.auth_provider = RemoteAuthProvider(
            token_verifier=self.verifier,
            authorization_servers=[settings.auth_issuer],
            base_url="http://localhost:8000",
            resource_name="database-mcp",
        )

    async def authenticate_bearer_token(self, bearer_token: str) -> AuthenticatedUser:
        access_token = await self.verifier.verify_token(bearer_token)
        if access_token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user_id = access_token.subject or access_token.claims.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject",
            )

        fingerprint = hashlib.sha256(bearer_token.encode("utf-8")).hexdigest()
        return AuthenticatedUser(
            user_id=user_id,
            scopes=set(access_token.scopes),
            token_fingerprint=fingerprint,
        )


async def get_current_user(
    authorization: str = Header(default="", alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    auth_service = AuthenticationService(settings)
    return await auth_service.authenticate_bearer_token(token)
