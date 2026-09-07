"""Create application_logs table for centralized diagnostics.

Revision ID: b49de121cf3e
Revises: a81bd942ce10
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b49de121cf3e"
down_revision: str | Sequence[str] | None = "a81bd942ce10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default="ERROR"),
        sa.Column("environment", sa.String(32), nullable=False, server_default="production"),
        sa.Column("service", sa.String(64), nullable=False, server_default="deckpilot-backend"),
        sa.Column("component", sa.String(64), nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=True),
        sa.Column("operation", sa.String(128), nullable=True),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("http_method", sa.String(16), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        # Context
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("job_id", sa.String(36), nullable=True),
        # Error
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        # External provider
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("provider_operation", sa.String(128), nullable=True),
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
        sa.Column("provider_request_id", sa.String(128), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        # Execution metrics
        sa.Column("started_at", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=True, server_default="1"),
        # Diagnostic context
        sa.Column("request_data", sa.Text(), nullable=True),
        sa.Column("additional_context", sa.Text(), nullable=True),
        # Resolution
        sa.Column("resolved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.Integer(), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
    )

    # Indexes
    op.create_index("ix_application_logs_correlation_id", "application_logs", ["correlation_id"])
    op.create_index("ix_application_logs_fingerprint", "application_logs", ["fingerprint"])
    op.create_index("ix_application_logs_timestamp", "application_logs", ["timestamp"])
    op.create_index("ix_application_logs_level", "application_logs", ["level"])
    op.create_index("ix_application_logs_environment", "application_logs", ["environment"])
    op.create_index("ix_application_logs_service", "application_logs", ["service"])
    op.create_index("ix_application_logs_agent_name", "application_logs", ["agent_name"])
    op.create_index("ix_application_logs_user_id", "application_logs", ["user_id"])
    op.create_index("ix_application_logs_project_id", "application_logs", ["project_id"])
    op.create_index("ix_application_logs_conversation_id", "application_logs", ["conversation_id"])
    op.create_index("ix_application_logs_job_id", "application_logs", ["job_id"])
    op.create_index("ix_application_logs_error_type", "application_logs", ["error_type"])
    op.create_index("ix_application_logs_provider", "application_logs", ["provider"])
    op.create_index("ix_application_logs_resolved", "application_logs", ["resolved"])


def downgrade() -> None:
    op.drop_index("ix_application_logs_resolved", table_name="application_logs")
    op.drop_index("ix_application_logs_provider", table_name="application_logs")
    op.drop_index("ix_application_logs_error_type", table_name="application_logs")
    op.drop_index("ix_application_logs_job_id", table_name="application_logs")
    op.drop_index("ix_application_logs_conversation_id", table_name="application_logs")
    op.drop_index("ix_application_logs_project_id", table_name="application_logs")
    op.drop_index("ix_application_logs_user_id", table_name="application_logs")
    op.drop_index("ix_application_logs_agent_name", table_name="application_logs")
    op.drop_index("ix_application_logs_service", table_name="application_logs")
    op.drop_index("ix_application_logs_environment", table_name="application_logs")
    op.drop_index("ix_application_logs_level", table_name="application_logs")
    op.drop_index("ix_application_logs_timestamp", table_name="application_logs")
    op.drop_index("ix_application_logs_fingerprint", table_name="application_logs")
    op.drop_index("ix_application_logs_correlation_id", table_name="application_logs")
    op.drop_table("application_logs")
