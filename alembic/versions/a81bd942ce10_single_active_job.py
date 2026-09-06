"""Enforce one active generation job per project.

Revision ID: a81bd942ce10
Revises: f7a1c5e9b203
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a81bd942ce10"
down_revision: str | Sequence[str] | None = "f7a1c5e9b203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("active_slot", sa.Integer(), nullable=True))
    op.create_index(
        "uq_generation_jobs_project_active",
        "generation_jobs",
        ["project_id", "active_slot"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_generation_jobs_project_active", table_name="generation_jobs")
    op.drop_column("generation_jobs", "active_slot")
