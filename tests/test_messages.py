"""Tests for messages endpoints."""

from fastapi.testclient import TestClient

from tests.test_projects import create_authenticated_user


def test_message_flow(client: TestClient):
    headers = create_authenticated_user(client, "messenger@deckpilot.ai")

    # Create project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Q3 Board Deck"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    # 1. Post user message
    msg1_resp = client.post(
        f"/api/v1/projects/{proj_id}/messages",
        json={"content": "Create a 10 slide deck on Q3 results", "role": "user"},
        headers=headers,
    )
    assert msg1_resp.status_code == 201
    msg1_data = msg1_resp.json()
    assert msg1_data["role"] == "user"
    assert msg1_data["content"] == "Create a 10 slide deck on Q3 results"
    assert msg1_data["project_id"] == proj_id

    # 2. Clients cannot forge assistant or system messages.
    msg2_resp = client.post(
        f"/api/v1/projects/{proj_id}/messages",
        json={"content": "I'm analyzing your request and structuring the narrative.", "role": "assistant"},
        headers=headers,
    )
    assert msg2_resp.status_code == 422

    # 3. List messages
    list_resp = client.get(f"/api/v1/projects/{proj_id}/messages", headers=headers)
    assert list_resp.status_code == 200
    messages = list_resp.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "Create a 10 slide deck on Q3 results"
    assert "attachments" in messages[0]
    assert messages[0]["attachments"] == []


def test_message_attachments_and_edit_flow(client: TestClient):
    headers = create_authenticated_user(client, "claude_flow@deckpilot.ai")

    # 1. Create project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Strategic Review"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    # 2. Upload two attachments
    att1_resp = client.post(
        f"/api/v1/projects/{proj_id}/attachments",
        files={"file": ("financials.md", b"# Financial Data\nRevenue: $10M", "text/markdown")},
        headers=headers,
    )
    assert att1_resp.status_code == 201
    att1 = att1_resp.json()
    att1_id = att1["id"]

    att2_resp = client.post(
        f"/api/v1/projects/{proj_id}/attachments",
        files={"file": ("roadmap.md", b"# Product Roadmap\nQ1: Alpha launch", "text/markdown")},
        headers=headers,
    )
    assert att2_resp.status_code == 201
    att2 = att2_resp.json()
    att2_id = att2["id"]

    # 3. Send chat message with both attachments
    chat_resp = client.post(
        f"/api/v1/projects/{proj_id}/chat",
        json={
            "content": "Analyze the attached financials and roadmap.",
            "has_attachments": True,
            "attachment_ids": [att1_id, att2_id],
            "mode": "ask",
        },
        headers=headers,
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    user_msg = chat_data["user_message"]
    user_msg_id = user_msg["id"]
    assert len(user_msg["attachments"]) == 2
    attached_names = {a["file_name"] for a in user_msg["attachments"]}
    assert attached_names == {"financials.md", "roadmap.md"}

    # 4. Verify list_messages preserves both attachments
    list_resp = client.get(f"/api/v1/projects/{proj_id}/messages", headers=headers)
    assert list_resp.status_code == 200
    msgs = list_resp.json()
    # Should have user message and assistant message
    user_in_list = next(m for m in msgs if m["id"] == user_msg_id)
    assert len(user_in_list["attachments"]) == 2

    # 5. User edits the message to remove financials.md and update content
    edit_resp = client.post(
        f"/api/v1/projects/{proj_id}/messages/{user_msg_id}/edit",
        json={
            "content": "Focus only on the product roadmap.",
            "removed_attachment_ids": [att1_id],
            "mode": "ask",
        },
        headers=headers,
    )
    assert edit_resp.status_code == 200
    edit_data = edit_resp.json()
    updated_user_msg = edit_data["user_message"]
    assert updated_user_msg["id"] == user_msg_id
    assert updated_user_msg["content"] == "Focus only on the product roadmap."
    assert len(updated_user_msg["attachments"]) == 1
    assert updated_user_msg["attachments"][0]["file_name"] == "roadmap.md"

    # 6. Verify financials.md was completely deleted
    get_deleted_att = client.get(f"/api/v1/projects/{proj_id}/attachments/{att1_id}", headers=headers)
    assert get_deleted_att.status_code == 404

    # 7. Verify list_messages reflects the edit
    list_resp2 = client.get(f"/api/v1/projects/{proj_id}/messages", headers=headers)
    assert list_resp2.status_code == 200
    msgs2 = list_resp2.json()
    user_msg_updated = next(m for m in msgs2 if m["id"] == user_msg_id)
    assert user_msg_updated["content"] == "Focus only on the product roadmap."
    assert len(user_msg_updated["attachments"]) == 1
    assert user_msg_updated["attachments"][0]["file_name"] == "roadmap.md"

