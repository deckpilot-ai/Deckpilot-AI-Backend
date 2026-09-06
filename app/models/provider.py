"""AI Provider, API Key, and Agent Route models."""

import time
import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), default="openai_compatible", nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    keys = relationship("AIKey", back_populates="provider", cascade="all, delete-orphan")


class AIKey(Base):
    __tablename__ = "ai_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_providers.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cooldown_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_health_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    provider = relationship("AIProvider", back_populates="keys")


class AgentRoute(Base):
    __tablename__ = "agent_routes"

    agent_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of candidate models/providers
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()), nullable=False)
