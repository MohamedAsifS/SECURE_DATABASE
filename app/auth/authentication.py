from __future__ import annotations

from fastmcp.server.auth import JWTVerifier, RemoteAuthProvider

from app.config import Settings, get_settings

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


def get_authentication_service() -> AuthenticationService:
    return AuthenticationService(get_settings())
