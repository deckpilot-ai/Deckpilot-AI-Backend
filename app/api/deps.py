"""API Dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import AUTH_COOKIE_NAME
from app.db.engine import get_db
from app.models.user import User
from app.services.auth_service import AuthService


def get_token(
    authorization: Annotated[str | None, Header()] = None,
    deckpilotai_token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> str | None:
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials.strip():
            return credentials.strip()
    if deckpilotai_token:
        return deckpilotai_token
    return None


def get_current_user(
    token: Annotated[str | None, Depends(get_token)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = AuthService.get_user_by_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
