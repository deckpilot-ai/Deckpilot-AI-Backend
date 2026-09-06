"""Test suite for database migrations using Alembic."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade():
    """Verify that migrations can upgrade from scratch and downgrade cleanly."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = str(backend_dir / "alembic.ini")
    test_db_file = backend_dir / "test_migration_run.db"

    if test_db_file.exists():
        test_db_file.unlink()

    test_db_url = f"sqlite:///{test_db_file.as_posix()}"

    # Setup alembic config overriding database url
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    engine = create_engine(test_db_url)

    try:
        # 1. Run upgrade head
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Expected 14 tables + alembic_version
        expected_tables = {
            "users",
            "sessions",
            "projects",
            "messages",
            "attachments",
            "generation_jobs",
            "agent_tasks",
            "deck_versions",
            "artifacts",
            "ai_providers",
            "ai_keys",
            "agent_routes",
            "usage_events",
            "audit_logs",
            "alembic_version",
        }
        for t in expected_tables:
            assert t in tables, f"Expected table '{t}' missing from migrated database"

        # Verify columns on users table
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        assert {"id", "email", "password_hash", "role", "status", "created_at", "updated_at"}.issubset(user_cols)

        # 2. Run downgrade to base
        command.downgrade(alembic_cfg, "base")
        tables_after_downgrade = inspect(engine).get_table_names()
        # Only alembic_version remains or empty
        non_alembic_tables = [t for t in tables_after_downgrade if t != "alembic_version"]
        assert len(non_alembic_tables) == 0, f"Tables still present after downgrade: {non_alembic_tables}"

        # 3. Re-upgrade to head
        command.upgrade(alembic_cfg, "head")
        tables_reupgraded = inspect(engine).get_table_names()
        for t in expected_tables:
            assert t in tables_reupgraded

    finally:
        engine.dispose()
        if test_db_file.exists():
            try:
                test_db_file.unlink()
            except OSError:
                # Windows can retain a SQLite handle briefly after disposal.
                pass
