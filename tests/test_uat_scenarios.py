"""User Acceptance Testing (UAT) Scenarios for deckpilotAI."""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.attachment_pipeline import process_attachment


def test_uat_01_first_time_user_pitch_deck(client: TestClient):
    """UAT-01: First-time user registers, creates deck from prompt, and exports PPTX."""
    # 1. Register
    reg = client.post("/api/v1/auth/register", json={
        "email": "sarah.founder@startup.io",
        "password": "SecurePassword#2026",
    }).json()
    assert "id" in reg

    # 2. Login
    login = client.post("/api/v1/auth/login", json={
        "email": "sarah.founder@startup.io",
        "password": "SecurePassword#2026",
    }).json()
    token = login["token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 3. Create Project
    project = client.post("/api/v1/projects", json={"title": "Series Seed Pitch Deck"}, headers=auth).json()
    project_id = project["id"]

    # 4. Request deck creation via prompt
    client.post(
        f"/api/v1/projects/{project_id}/messages",
        json={"content": "Create a 4-slide investor presentation highlighting our AI multi-agent architecture.", "role": "user"},
        headers=auth,
    )

    # 5. Start Generation
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"prompt": "Create a 4-slide investor presentation highlighting our AI multi-agent architecture.", "mode": "generate"},
        headers=auth,
    ).json()
    assert job["status"] == "completed"

    # 6. Download PPTX
    pptx = client.get(f"/api/v1/projects/{project_id}/decks/1/download", headers=auth)
    assert pptx.status_code == 200
    assert len(pptx.content) > 10000
    assert pptx.content.startswith(b"PK\x03\x04")


def test_uat_02_document_grounded_executive_review(client: TestClient, db_session: Session):
    """UAT-02: User attaches financial document and generates grounded PowerPoint deck."""
    # Register & Login
    client.post("/api/v1/auth/register", json={"email": "cfo@enterprise.com", "password": "EnterprisePassword!2026"})
    token = client.post("/api/v1/auth/login", json={"email": "cfo@enterprise.com", "password": "EnterprisePassword!2026"}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Create project
    proj_id = client.post("/api/v1/projects", json={"title": "Board Financial Review"}, headers=auth).json()["id"]

    # Upload document
    doc_bytes = b"Consolidated Financials:\nTotal Revenue: $24.5M (+45% YoY)\nGross Margin: 78%\nNet Retention: 122%"
    att = client.post(
        f"/api/v1/projects/{proj_id}/attachments",
        files={"file": ("q3_financial_model.txt", doc_bytes, "text/plain")},
        headers=auth,
    ).json()
    assert att["status"] == "pending"

    # Extraction runs detached in production; drive it inline for the test.
    asyncio.run(process_attachment(att["id"], db=db_session))
    refreshed = client.get(f"/api/v1/projects/{proj_id}/attachments/{att['id']}", headers=auth).json()
    assert refreshed["status"] == "ready"

    # Generate
    job = client.post(
        f"/api/v1/projects/{proj_id}/jobs",
        json={"prompt": "Generate a financial review presentation using the uploaded model.", "mode": "generate"},
        headers=auth,
    ).json()
    assert job["status"] == "completed"

    # Verify download
    pptx = client.get(f"/api/v1/projects/{proj_id}/decks/1/download", headers=auth)
    assert pptx.status_code == 200
    assert pptx.content.startswith(b"PK\x03\x04")


def test_uat_03_tenant_isolation_and_security(client: TestClient):
    """UAT-03: Strict user data isolation — User A cannot access User B's projects."""
    # Create User A
    client.post("/api/v1/auth/register", json={"email": "userA@test.com", "password": "PasswordA#2026"})
    tokenA = client.post("/api/v1/auth/login", json={"email": "userA@test.com", "password": "PasswordA#2026"}).json()["token"]
    authA = {"Authorization": f"Bearer {tokenA}"}
    projA_id = client.post("/api/v1/projects", json={"title": "Confidential Deck A"}, headers=authA).json()["id"]

    # Create User B
    client.post("/api/v1/auth/register", json={"email": "userB@test.com", "password": "PasswordB#2026"})
    tokenB = client.post("/api/v1/auth/login", json={"email": "userB@test.com", "password": "PasswordB#2026"}).json()["token"]
    authB = {"Authorization": f"Bearer {tokenB}"}

    # User B attempts to access User A's project -> MUST BE 404/403
    forbidden_get = client.get(f"/api/v1/projects/{projA_id}", headers=authB)
    assert forbidden_get.status_code == 404

    forbidden_delete = client.delete(f"/api/v1/projects/{projA_id}", headers=authB)
    assert forbidden_delete.status_code == 404
