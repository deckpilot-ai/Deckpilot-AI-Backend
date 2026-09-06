"""Authentication service."""

import hashlib
import time

import jwt
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest

_DUMMY_PASSWORD_HASH = hash_password("deckpilotai-dummy-password-for-timing-equalization")


class AuthService:
    @staticmethod
    def register(db: Session, req: RegisterRequest) -> User:
        existing = db.scalar(select(User).where(User.email == req.email.lower()))
        if existing:
            raise ValueError("Email already registered")

        user = User(
            email=req.email.lower(),
            password_hash=hash_password(req.password),
            role="user",
            status="active",
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Email already registered") from exc
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, req: LoginRequest) -> tuple[User, str]:
        user = db.scalar(select(User).where(User.email == req.email.lower()))
        if not user:
            verify_password(req.password, _DUMMY_PASSWORD_HASH)
            raise ValueError("Invalid email or password")
        if not verify_password(req.password, user.password_hash):
            raise ValueError("Invalid email or password")

        if user.status != "active":
            raise ValueError("Account is suspended")

        token = create_access_token(user_id=user.id, role=user.role)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = int(time.time())

        db.execute(
            delete(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.expires_at <= now,
            )
        )

        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + settings.jwt_expire_minutes * 60,
        )
        db.add(session)
        db.commit()

        return user, token

    @staticmethod
    def get_user_by_token(db: Session, token: str) -> User | None:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if not user_id:
                return None
        except jwt.PyJWTError:
            return None

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        session = db.scalar(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.token_hash == token_hash,
                UserSession.expires_at > now,
            )
        )
        if not session:
            return None

        return db.scalar(select(User).where(User.id == user_id, User.status == "active"))

    @staticmethod
    def logout(db: Session, token: str) -> None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
        if session:
            db.delete(session)
            db.commit()
