"""Database connection safety tests."""

import builtins

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import _create_engine, _LibSQLCursorAdapter, engine


def test_sqlite_foreign_keys_are_enabled() -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_configured_turso_never_silently_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fail_libsql_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "libsql":
            raise ImportError("simulated missing libsql driver")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(settings, "turso_database_url", "libsql://configured.invalid")
    monkeypatch.setattr(settings, "turso_auth_token", "configured-token")
    monkeypatch.setattr(builtins, "__import__", fail_libsql_import)

    with pytest.raises(ImportError, match="missing libsql"):
        _create_engine()


def test_libsql_adapter_converts_memoryview_bind_values() -> None:
    class RecordingCursor:
        def __init__(self) -> None:
            self.parameters = None

        def execute(self, _statement, parameters) -> None:
            self.parameters = parameters

    cursor = RecordingCursor()
    adapter = _LibSQLCursorAdapter(cursor)
    adapter.execute("INSERT INTO keys(secret) VALUES (?)", (memoryview(b"ciphertext"),))

    assert cursor.parameters == (b"ciphertext",)
