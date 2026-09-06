"""Compacted context model for long-running chat sessions (1M token window)."""

import time
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompactedContext(Base):
    __tablename__ = "compacted_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    compacted_until_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    estimated_tokens_compacted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    project = relationship("Project", back_populates="compacted_contexts")
