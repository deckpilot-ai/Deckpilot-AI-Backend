"""Verify live Turso Cloud database connectivity and tables via HTTP pipeline."""

import os
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_turso_live_schema() -> None:
    """Verify live Turso connectivity and the expected production schema."""
    backend_dir = Path(__file__).resolve().parent.parent
    load_dotenv(backend_dir / ".env")

    url = os.getenv("TURSO_DATABASE_URL", "").replace("libsql://", "https://")
    token = os.getenv("TURSO_AUTH_TOKEN", "")
    assert url, "TURSO_DATABASE_URL not set in .env"
    assert token, "TURSO_AUTH_TOKEN not set in .env"

    response = httpx.post(
        f"{url}/v2/pipeline",
        json={
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    },
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=10.0,
    )
    assert response.status_code == 200, f"Turso pipeline failed with status {response.status_code}"

    rows = response.json()["results"][0]["response"]["result"]["rows"]
    tables = {row[0]["value"] for row in rows}
    expected = {
        "agent_routes",
        "agent_tasks",
        "ai_keys",
        "ai_providers",
        "alembic_version",
        "artifacts",
        "attachments",
        "audit_logs",
        "deck_versions",
        "generation_jobs",
        "messages",
        "projects",
        "sessions",
        "usage_events",
        "users",
    }
    assert expected <= tables, f"Missing tables: {sorted(expected - tables)}"
