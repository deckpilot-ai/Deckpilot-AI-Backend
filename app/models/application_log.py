"""Application diagnostics and error log model for production observability."""

import time
import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationLog(Base):
    __tablename__ = "application_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    timestamp: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True, nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="ERROR", index=True, nullable=False)  # DEBUG | INFO | WARNING | ERROR | CRITICAL
    environment: Mapped[str] = mapped_column(String(32), default="production", index=True, nullable=False)
    service: Mapped[str] = mapped_column(String(64), default="deckpilot-backend", index=True, nullable=False)
    component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    operation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Context
    user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    # Error
    error_type: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # External provider
    provider: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    provider_operation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Execution metrics
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_number: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)
    max_attempts: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)

    # Diagnostic context (Sanitized JSON strings)
    request_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolution
    resolved: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)  # 0 = unresolved, 1 = resolved
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
