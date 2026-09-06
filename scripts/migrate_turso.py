"""Apply database schema and migrations directly to Turso Cloud database."""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401
from app.db.base import Base


def migrate_turso():
    load_dotenv(backend_dir / ".env")
    raw_url = os.getenv("TURSO_DATABASE_URL", "")
    token = os.getenv("TURSO_AUTH_TOKEN", "")

    if not raw_url or not token:
        print("ERROR: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN is missing from .env")
        sys.exit(1)

    turso_http_url = raw_url.replace("libsql://", "https://")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    dialect = sqlite.dialect()
    statements = []

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
        statements.append(ddl)
        for idx in table.indexes:
            idx_ddl = str(CreateIndex(idx).compile(dialect=dialect)).strip()
            statements.append(idx_ddl)

    # Add alembic_version table
    statements.append(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))"
    )
    statements.append(
        "INSERT OR REPLACE INTO alembic_version (version_num) VALUES ('d329d489d47d')"
    )

    print(f"Applying {len(statements)} DDL statements to Turso at {turso_http_url}...")

    requests = [{"type": "execute", "stmt": {"sql": stmt}} for stmt in statements]
    payload = {"requests": requests}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{turso_http_url}/v2/pipeline", json=payload, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()

        results = res_data.get("results", [])
        errors = []
        for i, res in enumerate(results):
            if res.get("type") == "error":
                errors.append((statements[i], res.get("error")))

        if errors:
            print(f"FAILED with {len(errors)} errors:")
            for stmt, err in errors:
                print(f"Statement: {stmt}\nError: {err}\n")
            sys.exit(1)

        print("SUCCESS! All tables and indexes successfully created on Turso Cloud.")

        # Verify tables
        verify_payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    },
                }
            ]
        }
        with httpx.Client(timeout=10.0) as client:
            v_resp = client.post(f"{turso_http_url}/v2/pipeline", json=verify_payload, headers=headers)
            v_data = v_resp.json()
            rows = v_data["results"][0]["response"]["result"]["rows"]
            table_names = [r[0]["value"] for r in rows]

        print(f"Verified {len(table_names)} tables in Turso Cloud:")
        for t in table_names:
            print(f"  - {t}")

    except Exception as e:  # noqa: BLE001 - top-level CLI error boundary
        print(f"Exception during Turso migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate_turso()
