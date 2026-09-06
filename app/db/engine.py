"""Database engine and session management for Turso and local SQLite."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


def _normalize_libsql_parameters(value: Any) -> Any:
    """Convert DB-API parameter containers into types accepted by libsql."""
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, tuple):
        return tuple(_normalize_libsql_parameters(item) for item in value)
    if isinstance(value, list):
        return [_normalize_libsql_parameters(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_libsql_parameters(item) for key, item in value.items()}
    return value


class _LibSQLCursorAdapter:
    """Normalize SQLAlchemy's binary bind values for the libsql DB-API."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, statement: str, parameters: Any = None) -> "_LibSQLCursorAdapter":
        if parameters is None:
            self._cursor.execute(statement)
        else:
            self._cursor.execute(statement, _normalize_libsql_parameters(parameters))
        return self

    def executemany(self, statement: str, parameters: Any) -> "_LibSQLCursorAdapter":
        self._cursor.executemany(statement, _normalize_libsql_parameters(parameters))
        return self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _LibSQLConnectionAdapter:
    """Add the one SQLite DB-API hook SQLAlchemy expects but libsql omits."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def create_function(self, *_args: object, **_kwargs: object) -> None:
        # SQLAlchemy registers REGEXP/FLOOR functions on SQLite connections.
        # The remote libSQL service provides SQL functions server-side.
        return None

    def cursor(self) -> _LibSQLCursorAdapter:
        return _LibSQLCursorAdapter(self._connection.cursor())

    def __getattr__(self, name: str) -> object:
        return getattr(self._connection, name)


def _create_engine() -> Engine:
    db_url = settings.database_url
    common = {"echo": settings.db_echo, "pool_pre_ping": True}

    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            **common,
        )

    if db_url.startswith("libsql"):
        if not settings.turso_auth_token:
            raise RuntimeError("TURSO_AUTH_TOKEN is required for a libSQL database")

        import libsql

        def connect() -> _LibSQLConnectionAdapter:
            connection = libsql.connect(
                database=db_url,
                auth_token=settings.turso_auth_token,
            )
            return _LibSQLConnectionAdapter(connection)

        return create_engine("sqlite://", creator=connect, poolclass=NullPool, **common)

    raise RuntimeError(f"Unsupported database URL scheme: {db_url.partition(':')[0]}")


engine = _create_engine()


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection: Any, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
