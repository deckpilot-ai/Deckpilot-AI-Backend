"""Comprehensive tests for presentation modes, scaling, and WebSocket isolation."""

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.services.renderer import PPTXRenderer
from app.services.ws_manager import ws_manager


def create_auth_headers(client: TestClient, email: str = "opus_test@deckpilot.ai") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password@123"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_ask_mode_only_researches_and_never_generates(client: TestClient):
    """Ask mode: AI researches and analyzes without creating presentation jobs."""
    headers = create_auth_headers(client, "ask_mode_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Ask Mode Research"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={
            "content": "What are the key differences between RAG and Long Context LLMs for enterprise search?",
            "mode": "ask",
            "has_attachments": False,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["mode"] == "ask"
    assert data["intent"] == "ask"
    assert data["should_generate"] is False
    assert data["assistant_message"] is not None
    assert len(data["assistant_message"]["content"]) > 30

    # Ensure no background generation job was created
    job_check = client.get(f"/api/v1/projects/{project_id}/jobs/active", headers=headers)
    assert job_check.status_code == 200
    assert job_check.json()["active"] is False


def test_plan_mode_produces_structured_deck_plan(client: TestClient):
    """Plan mode: AI formulates the narrative arc and slide outline for user review before building."""
    headers = create_auth_headers(client, "plan_mode_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Plan Mode Architecture"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={
            "content": "Plan a 10-slide enterprise presentation on migrating to Kubernetes and cloud-native architecture.",
            "mode": "plan",
            "has_attachments": False,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["mode"] == "plan"
    assert data["intent"] == "plan"
    assert data["should_generate"] is False
    assert data["assistant_message"] is not None
    assert data.get("plan_spec") is not None
    
    plan = data["plan_spec"]
    assert "slides" in plan
    assert len(plan["slides"]) >= 3
    for s in plan["slides"]:
        assert "purpose" in s
        assert "slideId" in s


def test_autopilot_mode_triggers_generation(client: TestClient):
    """Autopilot mode: Default mode doing end-to-end presentation generation."""
    headers = create_auth_headers(client, "autopilot_mode_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Autopilot Deck Session"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={
            "content": "Build an elite 8-slide board deck summarizing our Series A traction and hiring plan.",
            "mode": "autopilot",
            "has_attachments": False,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["mode"] == "autopilot"
    assert data["intent"] == "generate"
    assert data["should_generate"] is True
    assert data["assistant_message"] is None


def test_decision_questions_for_ambiguous_prompts(client: TestClient):
    """When a prompt is ambiguous, the system provides clickable decision questions."""
    headers = create_auth_headers(client, "decision_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Ambiguous Deck Request"},
        headers=headers,
    )
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={
            "content": "I need a deck for my startup",
            "mode": "autopilot",
            "has_attachments": False,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["decision_questions"] is not None
    assert len(data["decision_questions"]) > 0
    dq = data["decision_questions"][0]
    assert "question" in dq
    assert len(dq["options"]) >= 2


def test_websocket_realtime_connection_and_broadcast(client: TestClient):
    """Test WebSocket connection and live event broadcasting without heavy HTTP polling."""
    headers = create_auth_headers(client, "ws_test@deckpilot.ai")
    project_response = client.post(
        "/api/v1/projects",
        json={"title": "WebSocket Test"},
        headers=headers,
    )
    test_project_id = project_response.json()["id"]

    with client.websocket_connect(f"/api/v1/ws/projects/{test_project_id}") as websocket:
        # Connected: verify server sent connection handshake
        init_data = websocket.receive_json()
        assert init_data["type"] == "connected"
        assert init_data["project_id"] == test_project_id

        # Server broadcasts an agent progress update
        ws_manager.broadcast_sync(
            test_project_id,
            {
                "type": "agent_progress",
                "data": {
                    "agent_type": "slide_writer",
                    "status": "running",
                    "message": "Writing Slide 14: Enterprise Security Architecture",
                    "slide_index": 14,
                    "total_slides": 22,
                },
            },
        )

        received = websocket.receive_json()
        assert received["type"] == "agent_progress"
        assert received["data"]["agent_type"] == "slide_writer"
        assert received["data"]["slide_index"] == 14
        assert received["data"]["total_slides"] == 22


def test_websocket_rejects_unauthenticated_and_cross_tenant_clients(client: TestClient):
    """Project progress must never leak through an unauthenticated or foreign socket."""
    with (
        pytest.raises(WebSocketDisconnect) as unauthenticated,
        client.websocket_connect(f"/api/v1/ws/projects/{uuid.uuid4()}"),
    ):
        pass
    assert unauthenticated.value.code == 4401

    owner_headers = create_auth_headers(client, "ws_owner@deckpilot.ai")
    project = client.post(
        "/api/v1/projects",
        json={"title": "Private WebSocket Project"},
        headers=owner_headers,
    ).json()
    client.post("/api/v1/auth/logout", headers=owner_headers)

    create_auth_headers(client, "ws_outsider@deckpilot.ai")
    with (
        pytest.raises(WebSocketDisconnect) as forbidden,
        client.websocket_connect(f"/api/v1/ws/projects/{project['id']}"),
    ):
        pass
    assert forbidden.value.code == 4403


def test_22_slide_renderer_and_taxonomy():
    """Verify PPTXRenderer scales seamlessly to 22 slides with full layout taxonomy."""
    # Construct a 22-slide deck spec covering multiple layouts
    layouts = [
        "hero", "two_column", "metrics_grid", "timeline",
        "process_steps", "comparison", "bullet_split", "quote"
    ]
    
    slides_data = []
    for i in range(1, 23):
        layout = layouts[(i - 1) % len(layouts)]
        slides_data.append({
            "slideId": f"s_{i}",
            "chapter": f"Chapter {(i - 1) // 4 + 1}: Growth Engines",
            "purpose": f"Strategic Pillar {i}: High Velocity Execution",
            "message": f"Action headline {i}: McKinsey Minto Principle execution delivers 4.2x ROI.",
            "layoutHint": layout,
            "bullets": [
                f"Operational milestone {i}.A achieved with 99.9% uptime",
                f"Cross-functional synergy {i}.B across enterprise departments",
                f"Q3 projected efficiency gains exceeding {i * 5}%",
            ],
            "metrics": [
                {"value": f"+{i * 12}%", "label": "YoY Growth", "context": "Audited ARR"},
                {"value": f"{100 - i}%", "label": "Efficiency Rate", "context": "Automated pipeline"},
            ],
            "steps": [
                {"step": "Phase 1", "desc": "Discovery & Alignment"},
                {"step": "Phase 2", "desc": "Enterprise Deployment"},
                {"step": "Phase 3", "desc": "Global Scale"},
            ],
            "leftColumn": f"Core capability analysis and baseline metrics for pillar {i}.",
            "rightColumn": f"Target transformation roadmap and key stakeholder outcomes for pillar {i}.",
            "quote": "Disciplined execution creates enduring enterprise value.",
            "author": "Executive Leadership Team",
            "speakerNotes": f"Speaker Guidance: Highlight impact of pillar {i} on EBITDA margins and board governance.",
        })

    deck_spec = {
        "title": "Enterprise Transformation: 2026-2030 Strategic Roadmap",
        "slides": slides_data,
    }

    brand_style = {
        "colors": {
            "primary": "#0086FF",
            "secondary": "#0A0E1A",
            "accent": "#38BDF8",
            "background": "#FFFFFF",
        },
        "titleFont": {"name": "Calibri"},
    }

    pptx_bytes = PPTXRenderer.render_deck(deck_spec, brand_style)
    assert pptx_bytes is not None
    assert len(pptx_bytes) > 20000  # Substantial valid PPTX file size
    assert pptx_bytes[:4] == b"PK\x03\x04"  # Valid ZIP/OOXML header for .pptx


def test_22_slide_e2e_generation_pipeline(client: TestClient):
    """End-to-end test verifying 22-slide expansion, chunked generation, and download."""
    headers = create_auth_headers(client, "full_22_test@deckpilot.ai")

    # 1. Create project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "22-Slide Enterprise Strategy"},
        headers=headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Trigger 22-slide generation job
    job_resp = client.post(
        f"/api/v1/projects/{proj_id}/jobs",
        json={
            "prompt": "Create a comprehensive 22-slide enterprise pitch deck for our AI orchestration platform.",
            "mode": "generate",
        },
        headers=headers,
    )
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    assert job_data["status"] == "completed"
    # 3. Verify Deck Version has exactly 22 slides
    deck_resp = client.get(f"/api/v1/projects/{proj_id}/decks/1", headers=headers)
    assert deck_resp.status_code == 200
    deck_data = deck_resp.json()
    assert deck_data["version"] == 1
    slides = deck_data["spec"]["slides"]
    assert len(slides) == 22, f"Expected 22 slides, got {len(slides)}"

    # Verify slide taxonomy and notes
    for idx, slide in enumerate(slides, 1):
        assert "purpose" in slide or "title" in slide
        assert "layoutHint" in slide
        assert "speakerNotes" in slide
        assert len(slide["speakerNotes"]) > 10

    # 4. Download and verify binary PPTX integrity
    download_resp = client.get(f"/api/v1/projects/{proj_id}/decks/1/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.content.startswith(b"PK\x03\x04")
    assert len(download_resp.content) > 20000
