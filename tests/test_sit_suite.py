"""Comprehensive System Integration Testing (SIT) Suite for deckpilotAI.

Tests complete API flows, database persistence, live Cloudflare R2 file storage,
multi-agent generation DAG, and admin key management.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def test_sit_complete_system_flow(client: TestClient, db_session: Session):
    # -----------------------------------------------------------------------
    # SIT-01: Health Endpoint Check
    # -----------------------------------------------------------------------
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "deckpilotAI-backend"}

    # -----------------------------------------------------------------------
    # SIT-02: Authentication & Authorization Flow
    # -----------------------------------------------------------------------
    email = "sit_executive@deckpilot.ai"
    password = "StrongPassword2026!"

    # Register user
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg_resp.status_code == 201
    user_info = reg_resp.json()
    assert user_info["email"] == email
    assert user_info["role"] == "user"
    user_id = user_info["id"]

    # Admin assignment is an out-of-band privileged operation, never public registration.
    admin_user = db_session.get(User, user_id)
    assert admin_user is not None
    admin_user.role = "admin"
    db_session.commit()

    # Duplicate registration rejection
    dup_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert dup_resp.status_code == 409

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    assert "deckpilotai_token" in login_resp.cookies
    headers = {"Authorization": f"Bearer {token}"}

    # Verify /auth/me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user_id

    # -----------------------------------------------------------------------
    # SIT-03: Project Management Flow
    # -----------------------------------------------------------------------
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Q3 Growth Presentation"},
        headers=headers,
    )
    assert proj_resp.status_code == 201
    project = proj_resp.json()
    project_id = project["id"]
    assert project["title"] == "Q3 Growth Presentation"

    # List projects
    list_projs_resp = client.get("/api/v1/projects", headers=headers)
    assert list_projs_resp.status_code == 200
    assert any(p["id"] == project_id for p in list_projs_resp.json())

    # Update project
    patch_resp = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": "Q3 Executive Growth Deck"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Q3 Executive Growth Deck"

    # -----------------------------------------------------------------------
    # SIT-04: Chat Messaging Flow
    # -----------------------------------------------------------------------
    msg_resp = client.post(
        f"/api/v1/projects/{project_id}/messages",
        json={"content": "Please generate a 4-slide board presentation from our Q3 numbers.", "role": "user"},
        headers=headers,
    )
    assert msg_resp.status_code == 201
    assert msg_resp.json()["project_id"] == project_id

    msgs_list_resp = client.get(f"/api/v1/projects/{project_id}/messages", headers=headers)
    assert msgs_list_resp.status_code == 200
    assert len(msgs_list_resp.json()) == 1

    # -----------------------------------------------------------------------
    # SIT-05: Document Ingestion & Live Cloudflare R2 Upload Flow
    # -----------------------------------------------------------------------
    sample_doc = b"# Q3 Financial Performance\nRevenue: $4.2M\nARR: $16.8M\nGrowth: 110% YoY"
    att_resp = client.post(
        f"/api/v1/projects/{project_id}/attachments",
        files={"file": ("q3_performance.md", sample_doc, "text/markdown")},
        headers=headers,
    )
    assert att_resp.status_code == 201
    att = att_resp.json()
    assert att["status"] == "ready"
    assert att["file_name"] == "q3_performance.md"
    att_id = att["id"]

    # Verify attachment retrieval
    get_att_resp = client.get(f"/api/v1/projects/{project_id}/attachments/{att_id}", headers=headers)
    assert get_att_resp.status_code == 200
    assert get_att_resp.json()["id"] == att_id

    # -----------------------------------------------------------------------
    # SIT-06: Multi-Agent Generation Job & PPTX Rendering Flow
    # -----------------------------------------------------------------------
    job_resp = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"prompt": "Generate a 4-slide board presentation from our Q3 numbers.", "mode": "generate"},
        headers=headers,
    )
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    assert job_data["status"] == "completed"
    job_id = job_data["job_id"]

    # Inspect job tasks execution
    job_detail = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert job_detail["status"] == "completed"
    assert len(job_detail["tasks"]) == 8
    for t in job_detail["tasks"]:
        assert t["status"] == "completed"

    # Fetch rendered deck specification
    deck_resp = client.get(f"/api/v1/projects/{project_id}/decks/1", headers=headers)
    assert deck_resp.status_code == 200
    assert "slides" in deck_resp.json()["spec"]

    # Download rendered PPTX file
    pptx_resp = client.get(f"/api/v1/projects/{project_id}/decks/1/download", headers=headers)
    assert pptx_resp.status_code == 200
    assert pptx_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert pptx_resp.content.startswith(b"PK\x03\x04")

    # -----------------------------------------------------------------------
    # SIT-07: Admin AI Provider & Key Security Management
    # -----------------------------------------------------------------------
    prov_resp = client.post(
        "/api/v1/admin/providers",
        json={"name": "OpenRouter-Primary", "base_url": "https://openrouter.ai/api/v1", "priority": 10},
        headers=headers,
    )
    assert prov_resp.status_code == 201
    prov_id = prov_resp.json()["id"]

    # Add encrypted key
    key_resp = client.post(
        f"/api/v1/admin/providers/{prov_id}/keys",
        json={"label": "Production Primary Key", "secret": "sk-or-v1-secret-key-for-deckpilotai"},
        headers=headers,
    )
    assert key_resp.status_code == 201
    assert key_resp.json()["status"] == "added"
    key_id = key_resp.json()["id"]

    # Verify provider listing (secret is NEVER exposed)
    prov_list_resp = client.get("/api/v1/admin/providers", headers=headers)
    assert prov_list_resp.status_code == 200
    providers = prov_list_resp.json()
    target_prov = next(p for p in providers if p["id"] == prov_id)
    assert len(target_prov["keys"]) == 1
    assert "secret" not in target_prov["keys"][0]  # Verify zero secret leakage

    # Rotate without exposing the replacement, then revoke while retaining its audit record.
    rotate_resp = client.put(
        f"/api/v1/admin/providers/{prov_id}/keys/{key_id}",
        json={"label": "Rotated Primary Key", "secret": "sk-or-v1-rotated-secret-for-deckpilotai"},
        headers=headers,
    )
    assert rotate_resp.status_code == 200
    assert rotate_resp.json() == {"id": key_id, "label": "Rotated Primary Key", "status": "rotated"}
    assert "secret" not in rotate_resp.json()

    revoke_resp = client.delete(
        f"/api/v1/admin/providers/{prov_id}/keys/{key_id}",
        headers=headers,
    )
    assert revoke_resp.status_code == 204

    revoked_list = client.get("/api/v1/admin/providers", headers=headers).json()
    revoked_key = next(p for p in revoked_list if p["id"] == prov_id)["keys"][0]
    assert revoked_key["enabled"] is False

    # Configure route
    route_resp = client.put(
        "/api/v1/admin/routing/slide_writer",
        json={"candidates": [{"provider_id": prov_id, "model": "anthropic/claude-3.5-sonnet"}]},
        headers=headers,
    )
    assert route_resp.status_code == 200
    assert route_resp.json()["status"] == "updated"
