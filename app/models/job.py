"""Generation job and agent task models."""

import time
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        Index("uq_generation_jobs_project_idempotency", "project_id", "idempotency_key", unique=True),
        Index("uq_generation_jobs_project_active", "project_id", "active_slot", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    trigger_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), default="generate", nullable=False)  # generate | revise | export
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)  # queued | running | completed | failed | cancelled
    idempotency_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    active_slot: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    project = relationship("Project", back_populates="generation_jobs")
    tasks = relationship("AgentTask", back_populates="job", cascade="all, delete-orphan")


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (Index("uq_agent_tasks_job_agent", "job_id", "agent_type", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | running | completed | failed | skipped
    dependency_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    input_artifacts_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    output_artifacts_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_route_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job = relationship("GenerationJob", back_populates="tasks")
