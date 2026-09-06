"""initial_schema

Revision ID: d329d489d47d
Revises: 
Create Date: 2026-09-05 19:32:49.764906

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd329d489d47d'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all core tables for deckpilotAI."""
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='user'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. sessions
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)
    op.create_index('ix_sessions_token_hash', 'sessions', ['token_hash'], unique=False)

    # 3. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='Untitled Presentation'),
        sa.Column('current_deck_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'], unique=False)

    # 4. messages
    op.create_table(
        'messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_project_id', 'messages', ['project_id'], unique=False)

    # 5. attachments
    op.create_table(
        'attachments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('message_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='uploaded'),
        sa.Column('ownership_flag', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_attachments_project_id', 'attachments', ['project_id'], unique=False)
    op.create_index('ix_attachments_sha256', 'attachments', ['sha256'], unique=False)

    # 6. generation_jobs
    op.create_table(
        'generation_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('trigger_message_id', sa.String(length=36), nullable=True),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='generate'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('started_at', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_generation_jobs_project_id', 'generation_jobs', ['project_id'], unique=False)
    op.create_index('ix_generation_jobs_idempotency_key', 'generation_jobs', ['idempotency_key'], unique=False)

    # 7. agent_tasks
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('agent_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('dependency_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('input_artifacts_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('output_artifacts_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('provider_route_json', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('started_at', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['generation_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. deck_versions
    op.create_table(
        'deck_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('deck_json_artifact_id', sa.String(length=36), nullable=True),
        sa.Column('pptx_artifact_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deck_versions_project_id', 'deck_versions', ['project_id'], unique=False)

    # 9. artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('attachment_id', sa.String(length=36), nullable=True),
        sa.Column('job_id', sa.String(length=36), nullable=True),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=True),
        sa.Column('json_data', sa.Text(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('source_locator', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_artifacts_project_id', 'artifacts', ['project_id'], unique=False)

    # 10. ai_providers
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('base_url', sa.String(length=512), nullable=False),
        sa.Column('provider_type', sa.String(length=64), nullable=False, server_default='openai_compatible'),
        sa.Column('enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 11. ai_keys
    op.create_table(
        'ai_keys',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider_id', sa.String(length=36), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=False),
        sa.Column('encrypted_secret', sa.LargeBinary(), nullable=False),
        sa.Column('enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cooldown_until', sa.Integer(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.Integer(), nullable=True),
        sa.Column('last_health_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_keys_provider_id', 'ai_keys', ['provider_id'], unique=False)

    # 12. agent_routes
    op.create_table(
        'agent_routes',
        sa.Column('agent_type', sa.String(length=64), nullable=False),
        sa.Column('route_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('agent_type')
    )

    # 13. usage_events
    op.create_table(
        'usage_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('job_id', sa.String(length=36), nullable=True),
        sa.Column('provider_id', sa.String(length=36), nullable=True),
        sa.Column('key_id', sa.String(length=36), nullable=True),
        sa.Column('model', sa.String(length=128), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('input_units', sa.Integer(), nullable=True),
        sa.Column('output_units', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_usage_events_user_id', 'usage_events', ['user_id'], unique=False)
    op.create_index('ix_usage_events_created_at', 'usage_events', ['created_at'], unique=False)

    # 14. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('actor_user_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=128), nullable=False),
        sa.Column('target_type', sa.String(length=64), nullable=False),
        sa.Column('target_id', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_actor_user_id', 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('audit_logs')
    op.drop_table('usage_events')
    op.drop_table('agent_routes')
    op.drop_table('ai_keys')
    op.drop_table('ai_providers')
    op.drop_table('artifacts')
    op.drop_table('deck_versions')
    op.drop_table('agent_tasks')
    op.drop_table('generation_jobs')
    op.drop_table('attachments')
    op.drop_table('messages')
    op.drop_table('projects')
    op.drop_table('sessions')
    op.drop_table('users')
