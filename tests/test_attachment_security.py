"""Security and validation tests for file uploads."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deck import Artifact
from app.services.storage import StorageService, storage_service
from tests.test_projects import create_authenticated_user


@pytest.fixture
def project(client: TestClient) -> tuple[str, dict[str, str]]:
    headers = create_authenticated_user(client, "uploads@deckpilot.ai")
    response = client.post("/api/v1/projects", json={"title": "Uploads"}, headers=headers)
    return response.json()["id"], headers


def test_upload_rejects_empty_unsupported_and_mismatched_files(
    client: TestClient,
    project: tuple[str, dict[str, str]],
) -> None:
    project_id, headers = project
    endpoint = f"/api/v1/projects/{project_id}/attachments"

    empty = client.post(endpoint, files={"file": ("empty.txt", b"", "text/plain")}, headers=headers)
    assert empty.status_code == 422

    executable = client.post(
        endpoint,
        files={"file": ("payload.exe", b"MZ-not-allowed", "application/octet-stream")},
        headers=headers,
    )
    assert executable.status_code == 422

    fake_pdf = client.post(
        endpoint,
        files={"file": ("report.pdf", b"not a pdf", "application/pdf")},
        headers=headers,
    )
    assert fake_pdf.status_code == 422

    wrong_mime = client.post(
        endpoint,
        files={"file": ("notes.txt", b"safe text", "image/png")},
        headers=headers,
    )
    assert wrong_mime.status_code == 422


def test_upload_sanitizes_paths_and_enforces_size(
    client: TestClient,
    project: tuple[str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id, headers = project
    endpoint = f"/api/v1/projects/{project_id}/attachments"

    uploaded = client.post(
        endpoint,
        files={"file": ("../../quarterly brief.txt", b"Revenue grew 42%.", "text/plain")},
        headers=headers,
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["file_name"] == "quarterly brief.txt"
    assert ".." not in body["storage_key"]

    monkeypatch.setattr(settings, "max_upload_bytes", 8)
    oversized = client.post(
        endpoint,
        files={"file": ("large.txt", b"123456789", "text/plain")},
        headers=headers,
    )
    assert oversized.status_code == 413


def test_upload_rejects_corrupt_office_archive(
    client: TestClient,
    project: tuple[str, dict[str, str]],
) -> None:
    project_id, headers = project
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")

    response = client.post(
        f"/api/v1/projects/{project_id}/attachments",
        files={
            "file": (
                "fake.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_local_storage_rejects_path_traversal() -> None:
    storage = StorageService()
    assert not storage.use_r2
    with pytest.raises(ValueError, match="outside"):
        storage.put_bytes("../outside.txt", b"blocked")


def test_attachment_delete_removes_original_and_extracted_media(
    client: TestClient,
    project: tuple[str, dict[str, str]],
    db_session: Session,
) -> None:
    project_id, headers = project
    image_buffer = io.BytesIO()
    Image.new("RGB", (32, 24), color="blue").save(image_buffer, format="PNG")

    uploaded = client.post(
        f"/api/v1/projects/{project_id}/attachments",
        files={"file": ("diagram.png", image_buffer.getvalue(), "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 201
    attachment = uploaded.json()
    artifact_keys = db_session.scalars(
        select(Artifact.storage_key).where(
            Artifact.attachment_id == attachment["id"],
            Artifact.storage_key.is_not(None),
        )
    ).all()
    all_keys = {attachment["storage_key"], *(key for key in artifact_keys if key)}
    assert len(all_keys) == 2
    assert all(storage_service.get_bytes(key) for key in all_keys)

    deleted = client.delete(
        f"/api/v1/projects/{project_id}/attachments/{attachment['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    for key in all_keys:
        with pytest.raises(FileNotFoundError):
            storage_service.get_bytes(key)
