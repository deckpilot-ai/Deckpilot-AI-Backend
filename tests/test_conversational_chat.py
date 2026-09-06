"""Test conversational chat endpoint and intent detection."""

from fastapi.testclient import TestClient


def create_auth_headers(client: TestClient, email: str = "chat_user@deckpilot.ai") -> dict:
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


def test_greeting_does_not_trigger_presentation(client: TestClient):
    headers = create_auth_headers(client, "greeting_test@deckpilot.ai")

    # 1. Create a project
    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Greeting Test Session"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. User sends "hi"
    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={"content": "hi", "has_attachments": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["intent"] == "chat"
    assert data["should_generate"] is False
    assert data["user_message"]["content"] == "hi"
    assert data["assistant_message"] is not None
    assistant_content = data["assistant_message"]["content"]
    assert "deckpilotAI" in assistant_content or "presentation" in assistant_content.lower()

    # 3. Ensure no active jobs exist for this project
    job_check = client.get(f"/api/v1/projects/{project_id}/jobs/active", headers=headers)
    assert job_check.status_code == 200
    job_data = job_check.json()
    assert job_data["active"] is False
    assert job_data["job"] is None


def test_casual_question_does_not_trigger_presentation(client: TestClient):
    headers = create_auth_headers(client, "casual_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Casual Help Session"},
        headers=headers,
    )
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={"content": "can you help me?", "has_attachments": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["intent"] == "chat"
    assert data["should_generate"] is False
    assert data["assistant_message"] is not None


def test_explicit_presentation_request_triggers_generation(client: TestClient):
    headers = create_auth_headers(client, "deck_test@deckpilot.ai")

    proj_res = client.post(
        "/api/v1/projects",
        json={"title": "Pitch Deck Session"},
        headers=headers,
    )
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/v1/projects/{project_id}/chat",
        json={"content": "Create a 5-slide pitch deck for our AI SaaS startup", "has_attachments": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["intent"] == "generate"
    assert data["should_generate"] is True
    assert data["user_message"]["content"] == "Create a 5-slide pitch deck for our AI SaaS startup"
    assert data["assistant_message"] is None
