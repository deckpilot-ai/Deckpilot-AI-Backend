"""Deck version and extracted/generated artifact models."""

import time
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeckVersion(Base):
    __tablename__ = "deck_versions"
    __table_args__ = (Index("uq_deck_versions_project_version", "project_id", "version", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deck_json_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pptx_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)  # draft | ready | failed
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    project = relationship("Project", back_populates="deck_versions")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    attachment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("attachments.id", ondelete="CASCADE"), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # text_block | image | table | chart | font | deck_json | pptx | slide_preview
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    json_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    attachment = relationship("Attachment", back_populates="artifacts")
