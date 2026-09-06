"""Pytest fixtures for backend test suite."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Keep the default suite isolated even when a developer has live credentials in
# .env. Credentialed checks opt in with RUN_LIVE_TESTS=1.
if os.getenv("RUN_LIVE_TESTS") != "1":
    os.environ.update(
        {
            "APP_ENV": "test",
            "TURSO_DATABASE_URL": "",
            "TURSO_AUTH_TOKEN": "",
            "R2_ENDPOINT_URL": "",
            "R2_ACCESS_KEY_ID": "",
            "R2_SECRET_ACCESS_KEY": "",
            "OPENROUTER_API_KEY": "",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "MISTRAL_API_KEY": "",
            "JWT_SECRET": "test-jwt-secret-at-least-32-characters-long",
            "KEY_ENCRYPTION_SECRET": "test-encryption-secret-at-least-32-characters",
        }
    )

from app.core.rate_limit import action_rate_limiter, auth_rate_limiter
from app.db.base import Base
from app.db.engine import get_db
from app.main import app
from app.services.orchestrator import JobOrchestrator

# In-memory SQLite database for fast, isolated tests
TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def enable_test_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    JobOrchestrator.set_session_factory(TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session):
    auth_rate_limiter.reset()
    action_rate_limiter.reset()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    auth_rate_limiter.reset()
    action_rate_limiter.reset()
