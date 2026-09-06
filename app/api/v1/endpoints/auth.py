"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_token
from app.core.config import settings
from app.core.rate_limit import auth_rate_limiter
from app.core.security import AUTH_COOKIE_NAME
from app.db.engine import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _enforce_auth_rate_limit(
    request: Request,
    email: str,
    *,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"{action}:{client_host}:{email.strip().lower()}"
    retry_after = auth_rate_limiter.check(key, limit=limit, window_seconds=window_seconds)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserOut:
    _enforce_auth_rate_limit(request, req.email, action="register", limit=5, window_seconds=3600)
    try:
        user = AuthService.register(db, req)
        return UserOut.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/login", response_model=AuthResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    _enforce_auth_rate_limit(request, req.email, action="login", limit=10, window_seconds=300)
    try:
        user, token = AuthService.login(db, req)
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="none" if settings.is_secure_environment else "lax",
            secure=settings.is_secure_environment,
            max_age=settings.jwt_expire_minutes * 60,
            path="/",
        )
        return AuthResponse(user=UserOut.model_validate(user), token=token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout")
def logout(
    response: Response,
    token: Annotated[str | None, Depends(get_token)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    if token:
        AuthService.logout(db, token)
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        samesite="none" if settings.is_secure_environment else "lax",
        secure=settings.is_secure_environment,
    )
    return {"status": "ok", "message": "Logged out"}


@router.get("/me", response_model=UserOut)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    return UserOut.model_validate(current_user)
