"""Test suite for ChatGPT-style session mechanics, background job execution, and 1M context compaction."""

import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.services.compaction import ContextCompactionService


def create_auth_user(client: TestClient, email: str = "session_user@deckpilot.ai") -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password12345"})
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "password12345"})
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_background_job_and_active_endpoint(client: TestClient, db_session: Session):
    """Verify non-blocking job launch (202 Accepted) and active job query."""
    headers = create_auth_user(client, "bg_user@deckpilot.ai")

    # 1. Create project
    proj_res = client.post("/api/v1/projects", json={"title": "Cloud SaaS Strategy"}, headers=headers)
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Check active jobs before starting
    active_res = client.get(f"/api/v1/projects/{project_id}/jobs/active", headers=headers)
    assert active_res.status_code == 200
    assert active_res.json()["active"] is False

    # 3. Trigger background generation job
    job_res = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"prompt": "Build a 4-slide strategy presentation for enterprise SaaS.", "background": True},
        headers=headers,
    )
    assert job_res.status_code == 202
    job_data = job_res.json()
    assert job_data["status"] == "queued"
    job_id = job_data["job_id"]

    # 4. Query active job immediately
    active_res2 = client.get(f"/api/v1/projects/{project_id}/jobs/active", headers=headers)
    assert active_res2.status_code == 200
    assert active_res2.json()["job"]["id"] == job_id
    assert len(active_res2.json()["job"]["tasks"]) == 8

    # 5. Cancel or inspect the job cleanly
    cancel_res = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] in ("cancelled", "completed")

    job_detail = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_detail.status_code == 200
    assert job_detail.json()["status"] in ("cancelled", "completed")


def test_job_cancellation_endpoint(client: TestClient, db_session: Session):
    """Verify that a user can explicitly cancel an in-progress job."""
    headers = create_auth_user(client, "cancel_user@deckpilot.ai")

    proj_res = client.post("/api/v1/projects", json={"title": "Cancel Test Project"}, headers=headers)
    project_id = proj_res.json()["id"]

    # Start a job in background mode
    job_res = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"prompt": "Draft an investment deck.", "background": True},
        headers=headers,
    )
    assert job_res.status_code == 202
    job_id = job_res.json()["job_id"]

    cancel_res = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] in ("cancelled", "completed")


def test_1m_context_compaction_service(db_session: Session):
    """Verify 1M context tracking and automatic compaction synthesis."""
    user = User(
        id=str(uuid.uuid4()),
        email="compact_user@deckpilot.ai",
        password_hash=hash_password("password123"),
        role="user",
        status="active",
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )
    db_session.add(user)
    db_session.commit()

    project = Project(user_id=user.id, title="Compaction Enterprise Session")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Add 13 conversation messages to exceed MSG_THRESHOLD (10)
    now = int(time.time())
    messages_content = [
        ("user", "We are building an AI presentation engine for Series A funding."),
        ("assistant", "Understood. Analyzing target metrics and executive requirements."),
        ("user", "Ensure we highlight our 50% YoY revenue growth and $4M ARR benchmark."),
        ("assistant", "Captured metrics: 50% YoY growth, $4M ARR benchmark."),
        ("user", "Use a sleek dark mode theme with electric blue accents and modern sans typography."),
        ("assistant", "Theme set: Dark mode, electric blue accent, modern typography."),
        ("user", "Slide 1 should be a bold Hero slide with our mission statement."),
        ("assistant", "Slide 1 planned as Hero layout."),
        ("user", "Slide 2 should compare our market traction in a two-column layout."),
        ("assistant", "Slide 2 set to two-column layout."),
        ("user", "Slide 3 should show a timeline of our international expansion roadmap."),
        ("assistant", "Slide 3 planned as milestone timeline."),
        ("user", "Please finalize the deck with 4 slides total."),
    ]

    for i, (role, text) in enumerate(messages_content):
        m = Message(
            project_id=project.id,
            user_id=user.id if role == "user" else None,
            role=role,
            content=text,
            created_at=now + i,
        )
        db_session.add(m)
    db_session.commit()

    # Calculate session volume
    volume = ContextCompactionService.calculate_session_volume(db_session, project.id)
    assert volume["total_messages"] == 13
    assert volume["estimated_tokens"] > 0

    # Trigger compaction
    compaction = ContextCompactionService.compact_if_needed(db_session, project.id)
    assert compaction is not None
    assert "Session Context Summary" in compaction.summary_text
    assert "Primary Objectives" in compaction.summary_text
    assert compaction.estimated_tokens_compacted > 0

    # Check effective working context
    eff_context = ContextCompactionService.get_effective_context(db_session, project.id)
    assert "summary_text" in eff_context
    assert len(eff_context["recent_messages"]) <= 6
    assert len(eff_context["context_prompt"]) > 0
