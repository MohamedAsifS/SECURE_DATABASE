from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.auth.authentication import AuthenticationService, get_authentication_service


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    scopes: set[str]


async def get_current_user(
    authorization: str = Header(default="", alias="Authorization"),
    auth_service: AuthenticationService = Depends(get_authentication_service),
) -> AuthenticatedUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    access_token = await auth_service.verifier.verify_token(token)
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = access_token.subject or access_token.claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    return AuthenticatedUser(user_id=user_id, scopes=set(access_token.scopes))
