"""System Lock model for distributed synchronization across backend instances."""

import time
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.db.base import Base


class SystemLock(Base):
    __tablename__ = "system_locks"

    lock_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    locked_by: Mapped[str] = mapped_column(String(128), nullable=False)
    locked_until: Mapped[int] = mapped_column(Integer, nullable=False)
    acquired_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    @classmethod
    def acquire(
        cls,
        db: Session,
        lock_name: str,
        locked_by: str,
        lease_seconds: int = 55,
    ) -> bool:
        """Attempt to acquire or refresh a distributed lock.

        Returns True if acquired, False otherwise.
        """
        now = int(time.time())
        expires_at = now + lease_seconds

        try:
            lock = db.scalar(select(cls).where(cls.lock_name == lock_name))
            if not lock:
                lock = cls(
                    lock_name=lock_name,
                    locked_by=locked_by,
                    locked_until=expires_at,
                    acquired_at=now,
                )
                db.add(lock)
                db.commit()
                return True

            # Existing lock - check if expired or already owned by this instance
            if lock.locked_until <= now or lock.locked_by == locked_by:
                lock.locked_by = locked_by
                lock.locked_until = expires_at
                lock.acquired_at = now
                db.commit()
                return True

            # Currently held by another live instance
            return False
        except Exception:
            db.rollback()
            return False

    @classmethod
    def release(cls, db: Session, lock_name: str, locked_by: str) -> None:
        """Release a distributed lock if held by this instance."""
        try:
            lock = db.scalar(select(cls).where(cls.lock_name == lock_name, cls.locked_by == locked_by))
            if lock:
                lock.locked_until = int(time.time()) - 1
                db.commit()
        except Exception:
            db.rollback()
