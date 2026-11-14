from fastapi import HTTPException, status
from fastmcp.server.dependencies import get_access_token

SCOPE_SCHEMA_READ = "database:schema:read"
SCOPE_DATA_READ = "database:data:read"


class ScopeAuthorizer:
    @staticmethod
    def require_scope(user_scopes: set[str], required_scope: str) -> None:
        if required_scope not in user_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}",
            )

    @staticmethod
    def require_mcp_scope(required_scope: str) -> str:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError("Authentication required")

        if required_scope not in set(access_token.scopes):
            raise PermissionError(f"Missing required scope: {required_scope}")

        user_id = access_token.subject or access_token.claims.get("sub")
        if not user_id:
            raise PermissionError("Token missing subject")
        return user_id
