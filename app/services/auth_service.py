"""Authentication service."""

import hashlib
import secrets
import time
from typing import Any

import httpx
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
    def verify_google_credential(credential: str) -> dict[str, Any]:
        """Verify a Google credential (either ID Token JWT or OAuth2 access token) against Google's API."""
        if not credential or not credential.strip():
            raise ValueError("Empty Google credential.")

        cred_str = credential.strip()
        is_id_token = cred_str.count(".") == 2

        try:
            with httpx.Client(timeout=10.0) as client:
                if is_id_token:
                    resp = client.get(
                        "https://oauth2.googleapis.com/tokeninfo",
                        params={"id_token": cred_str},
                    )
                else:
                    resp = client.get(
                        "https://oauth2.googleapis.com/tokeninfo",
                        params={"access_token": cred_str},
                    )
        except Exception as exc:
            raise ValueError(f"Unable to reach Google authentication service: {exc}") from exc

        if resp.status_code != 200:
            error_detail = "Invalid Google token."
            try:
                err_data = resp.json()
                if "error_description" in err_data:
                    error_detail = err_data["error_description"]
            except Exception:
                pass
            raise ValueError(error_detail)

        info = resp.json()

        if is_id_token:
            iss = info.get("iss", "")
            if iss not in ("accounts.google.com", "https://accounts.google.com"):
                raise ValueError("Invalid Google token issuer.")

        # Verify audience or azp against configured client_id
        if settings.google_client_id and settings.google_client_id.strip():
            expected_id = settings.google_client_id.strip()
            aud = info.get("aud", "")
            azp = info.get("azp", "")
            if aud != expected_id and azp != expected_id:
                raise ValueError("Google token was not issued for this application.")

        # If userinfo (name / picture) is not present in tokeninfo response for an access token,
        # fetch userinfo from Google's userinfo endpoint
        if not info.get("name") and not is_id_token:
            try:
                with httpx.Client(timeout=5.0) as client:
                    u_resp = client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {cred_str}"},
                    )
                    if u_resp.status_code == 200:
                        u_data = u_resp.json()
                        if u_data.get("name"):
                            info["name"] = u_data["name"]
                        if u_data.get("picture"):
                            info["picture"] = u_data["picture"]
            except Exception:
                pass

        return info

    @staticmethod
    def authenticate_google(db: Session, credential: str) -> tuple[User, str]:
        """Authenticate via Google ID token. Auto-registers new users, logs in existing users."""
        token_info = AuthService.verify_google_credential(credential)
        email = (token_info.get("email") or "").strip().lower()
        if not email:
            raise ValueError("Google account did not provide an email address.")

        email_verified = token_info.get("email_verified")
        if email_verified not in (True, "true", "True", 1):
            raise ValueError("Google account email is not verified.")

        user = db.scalar(select(User).where(User.email == email))
        if not user:
            # Auto-register new Google user with secure random password hash
            random_pw = secrets.token_urlsafe(32)
            user = User(
                email=email,
                password_hash=hash_password(random_pw),
                role="user",
                status="active",
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = db.scalar(select(User).where(User.email == email))
            else:
                db.refresh(user)

        if not user:
            raise ValueError("Failed to create or find user account.")

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
