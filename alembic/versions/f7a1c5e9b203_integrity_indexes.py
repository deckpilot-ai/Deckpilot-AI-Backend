"""Add uniqueness and query-path indexes.

Revision ID: f7a1c5e9b203
Revises: d329d489d47d
Create Date: 2026-09-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f7a1c5e9b203"
down_revision: str | Sequence[str] | None = "d329d489d47d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("uq_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index(
        "uq_generation_jobs_project_idempotency",
        "generation_jobs",
        ["project_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "uq_agent_tasks_job_agent",
        "agent_tasks",
        ["job_id", "agent_type"],
        unique=True,
    )
    op.create_index(
        "uq_deck_versions_project_version",
        "deck_versions",
        ["project_id", "version"],
        unique=True,
    )
    op.create_index("ix_messages_project_created", "messages", ["project_id", "created_at"])
    op.create_index("ix_attachments_project_created", "attachments", ["project_id", "created_at"])
    op.create_index(
        "ix_generation_jobs_project_status_created",
        "generation_jobs",
        ["project_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_project_status_created", table_name="generation_jobs")
    op.drop_index("ix_attachments_project_created", table_name="attachments")
    op.drop_index("ix_messages_project_created", table_name="messages")
    op.drop_index("uq_deck_versions_project_version", table_name="deck_versions")
    op.drop_index("uq_agent_tasks_job_agent", table_name="agent_tasks")
    op.drop_index("uq_generation_jobs_project_idempotency", table_name="generation_jobs")
    op.drop_index("uq_sessions_token_hash", table_name="sessions")
