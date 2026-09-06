"""Utility script to create or reset a user account in the database."""

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.security import hash_password
from app.db.engine import SessionLocal
from app.models.user import User


def create_or_update_user(email: str, password: str, role: str = "admin"):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        now = int(time.time())
        pwd_hash = hash_password(password)

        if user:
            user.password_hash = pwd_hash
            user.role = role
            user.status = "active"
            user.updated_at = now
            print(f"Updated existing user '{email}' (role: {role}).")
        else:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=pwd_hash,
                role=role,
                status="active",
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            print(f"Created new user '{email}' (role: {role}).")

        db.commit()
        print(f"User ID: {user.id}")

        # Also sync to Turso Cloud if configured
        raw_url = os.getenv("TURSO_DATABASE_URL", "")
        token = os.getenv("TURSO_AUTH_TOKEN", "")
        if raw_url and token and not raw_url.startswith("sqlite"):
            try:
                import httpx
                turso_http = raw_url.replace("libsql://", "https://")
                sql = (
                    "INSERT OR REPLACE INTO users (id, email, password_hash, role, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)"
                )
                payload = {
                    "requests": [
                        {
                            "type": "execute",
                            "stmt": {
                                "sql": sql,
                                "args": [
                                    {"type": "text", "value": user.id},
                                    {"type": "text", "value": user.email},
                                    {"type": "text", "value": user.password_hash},
                                    {"type": "text", "value": user.role},
                                    {"type": "text", "value": user.status},
                                    {"type": "integer", "value": str(user.created_at)},
                                    {"type": "integer", "value": str(user.updated_at)},
                                ],
                            },
                        }
                    ]
                }
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                t_resp = httpx.post(f"{turso_http}/v2/pipeline", json=payload, headers=headers, timeout=10.0)
                if t_resp.status_code == 200 and t_resp.json().get("results", [{}])[0].get("type") == "ok":
                    print(f"Successfully synced user '{email}' to Turso Cloud!")
            except Exception as e:  # noqa: BLE001 - this optional CLI sync should still leave the local user usable
                print(f"Note: Turso sync skipped or error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update user account")
    parser.add_argument("--email", default="admin@creatorpilot.ai", help="User email")
    parser.add_argument("--password", default="Admin@123456", help="User password")
    parser.add_argument("--role", default="admin", choices=["user", "admin"], help="User role")
    args = parser.parse_args()

    create_or_update_user(args.email, args.password, args.role)
