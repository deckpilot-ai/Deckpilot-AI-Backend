"""Regression tests for design-preset project authorization and uploads."""

import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.design_presets import auto_configure_design
from app.core.security import hash_password
from app.models.project import Project
from app.models.user import User
from app.services.design_preset_registry import DesignPresetRegistry


@pytest.fixture
def user_factory(db_session: Session):
    def create_user(email: str, role: str = "user") -> User:
        user = User(
            email=email,
            password_hash=hash_password("password12345"),
            role=role,
            status="active",
        )
        db_session.add(user)
        db_session.flush()
        return user

    return create_user


@pytest.fixture
def project_factory(db_session: Session):
    def create_project(user: User, title: str = "Test presentation") -> Project:
        project = Project(user_id=user.id, title=title)
        db_session.add(project)
        db_session.flush()
        return project

    return create_project


@pytest.fixture
def login(client: TestClient):
    def authenticate(user: User) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "password12345"},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['token']}"}

    return authenticate


@pytest.fixture
def imported_preset() -> dict[str, str]:
    return {"id": "preset_test", "name": "Test preset"}


def test_owner_can_auto_configure_for_owned_project(
    client: TestClient,
    user_factory,
    project_factory,
    login,
    imported_preset,
):
    owner = user_factory("design-owner@deckpilot.ai")
    project = project_factory(owner)
    pptx_bytes = b"valid-looking-pptx" * 100

    with patch(
        "app.api.v1.endpoints.design_presets.DesignAutoConfigurator.configure_from_pptx",
        return_value=imported_preset,
    ) as configure:
        response = client.post(
            "/api/v1/design/auto-configure",
            files={
                "file": (
                    "reference.pptx",
                    pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
            data={"project_id": project.id},
            headers=login(owner),
        )

    assert response.status_code == 201
    assert response.json()["preset"] == imported_preset
    configure.assert_called_once_with(
        pptx_source=pptx_bytes,
        name="reference",
        project_id=project.id,
    )


def test_regular_user_cannot_auto_configure_for_foreign_project(
    client: TestClient,
    user_factory,
    project_factory,
    login,
):
    owner = user_factory("design-project-owner@deckpilot.ai")
    other_user = user_factory("design-other-user@deckpilot.ai")
    project = project_factory(owner)

    with patch(
        "app.api.v1.endpoints.design_presets.DesignAutoConfigurator.configure_from_pptx"
    ) as configure:
        response = client.post(
            "/api/v1/design/auto-configure",
            files={"file": ("reference.pptx", b"x" * 1000, "application/octet-stream")},
            data={"project_id": project.id},
            headers=login(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    configure.assert_not_called()


def test_admin_can_apply_preset_to_foreign_project(
    client: TestClient,
    user_factory,
    project_factory,
    login,
    imported_preset,
):
    owner = user_factory("design-apply-owner@deckpilot.ai")
    admin = user_factory("design-admin@deckpilot.ai", role="admin")
    project = project_factory(owner)

    with patch.object(DesignPresetRegistry, "get_preset", return_value=imported_preset):
        response = client.post(
            f"/api/v1/design/projects/{project.id}/apply-preset",
            params={"preset_id": imported_preset["id"]},
            headers=login(admin),
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "applied",
        "project_id": project.id,
        "preset_id": imported_preset["id"],
        "preset_name": imported_preset["name"],
    }


def test_regular_user_cannot_apply_preset_to_foreign_project(
    client: TestClient,
    user_factory,
    project_factory,
    login,
    imported_preset,
):
    owner = user_factory("design-apply-owner-2@deckpilot.ai")
    other_user = user_factory("design-apply-other@deckpilot.ai")
    project = project_factory(owner)

    with patch.object(DesignPresetRegistry, "get_preset", return_value=imported_preset) as get_preset:
        response = client.post(
            f"/api/v1/design/projects/{project.id}/apply-preset",
            params={"preset_id": imported_preset["id"]},
            headers=login(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    get_preset.assert_not_called()


def test_auto_configure_rejects_upload_without_filename(db_session: Session, user_factory):
    user = user_factory("design-no-filename@deckpilot.ai")
    upload = UploadFile(filename=None, file=BytesIO(b"x" * 1000))

    with (
        patch("app.api.v1.endpoints.design_presets.DesignAutoConfigurator.configure_from_pptx") as configure,
        pytest.raises(HTTPException) as error,
    ):
        asyncio.run(auto_configure_design(file=upload, current_user=user, db=db_session))

    assert error.value.status_code == 400
    assert error.value.detail == "Uploaded file must be a PowerPoint presentation (.pptx)"
    configure.assert_not_called()
