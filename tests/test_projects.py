"""Tests for projects endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.services.storage import storage_service


def create_authenticated_user(client: TestClient, email: str = "creator@deckpilot.ai") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password12345"},
    )
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_project_crud(client: TestClient):
    headers = create_authenticated_user(client, "user_proj@deckpilot.ai")

    # 1. Create project
    create_resp = client.post(
        "/api/v1/projects",
        json={"title": "Series A Pitch Deck"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    proj_id = proj_data["id"]
    assert proj_data["title"] == "Series A Pitch Deck"

    # 2. List projects
    list_resp = client.get("/api/v1/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 1
    assert projects[0]["id"] == proj_id

    # 3. Get single project
    get_resp = client.get(f"/api/v1/projects/{proj_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == proj_id

    # 4. Update project title
    update_resp = client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"title": "Updated Pitch Deck"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Pitch Deck"

    # 5. Store a project object and then delete the project.
    upload_resp = client.post(
        f"/api/v1/projects/{proj_id}/attachments",
        files={"file": ("cleanup.txt", b"delete this with the project", "text/plain")},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    storage_key = upload_resp.json()["storage_key"]
    assert storage_service.get_bytes(storage_key)

    # 6. Delete project and its object storage.
    delete_resp = client.delete(f"/api/v1/projects/{proj_id}", headers=headers)
    assert delete_resp.status_code == 204
    with pytest.raises(FileNotFoundError):
        storage_service.get_bytes(storage_key)

    # 7. Verify deletion
    verify_resp = client.get(f"/api/v1/projects/{proj_id}", headers=headers)
    assert verify_resp.status_code == 404
