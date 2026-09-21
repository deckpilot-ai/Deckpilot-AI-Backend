"""Unit and integration tests for the DataCleaner policy and storage optimization service."""

import json
import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.deck import Artifact, DeckVersion
from app.models.project import Project
from app.models.user import User
from app.services.data_cleaner import DataCleanerService
from app.services.storage import storage_service


def create_test_user_and_project(db: Session, title: str = "Test Project") -> tuple[User, Project]:
    """Create and persist a valid User and Project for foreign key compliance."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"user_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="test_hash",
        role="user",
    )
    db.add(user)
    db.flush()

    project = Project(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=title,
    )
    db.add(project)
    db.flush()
    return user, project


import hashlib
from app.models.session import UserSession


@pytest.fixture
def admin_auth_headers(db_session: Session) -> dict[str, str]:
    """Create an admin user, active session, and return bearer auth headers."""
    admin_user = User(
        id=str(uuid.uuid4()),
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="test_hash",
        role="admin",
        status="active",
    )
    db_session.add(admin_user)
    db_session.flush()

    token = create_access_token(admin_user.id, role="admin")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user_session = UserSession(
        id=str(uuid.uuid4()),
        user_id=admin_user.id,
        token_hash=token_hash,
        expires_at=int(time.time()) + 86400,
    )
    db_session.add(user_session)
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}


def test_get_used_asset_identifiers(db_session: Session):
    """Verify that images referenced in deck_json slides are correctly identified as used."""
    user, project = create_test_user_and_project(db_session, "Deck Spec Test")

    deck_spec = {
        "slides": [
            {
                "slideId": "s1",
                "headline": "Title Slide",
                "imageArtifactId": "art_used_001",
                "storage_key": "extracted/used_cover.png",
            },
            {
                "slideId": "s2",
                "headline": "Content Slide",
                "image_artifact_id": "art_used_002",
                "image_refs": [
                    {"artifact_id": "art_used_003", "storage_key": "extracted/chart_ref.png"}
                ],
            },
        ]
    }

    deck_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=project.id,
        type="deck_json",
        json_data=json.dumps(deck_spec),
        created_at=int(time.time()),
    )
    db_session.add(deck_art)
    db_session.commit()

    used_ids, used_keys = DataCleanerService.get_used_asset_identifiers(db_session)
    assert "art_used_001" in used_ids
    assert "art_used_002" in used_ids
    assert "art_used_003" in used_ids
    assert "extracted/used_cover.png" in used_keys
    assert "extracted/chart_ref.png" in used_keys
    assert "art_unused_999" not in used_ids


def test_cleaner_deletes_unused_old_images(db_session: Session):
    """Verify that unused document image artifacts older than 3 days are purged."""
    user, project = create_test_user_and_project(db_session, "Cleanup Test")

    # 4 days ago (older than 3 days cutoff)
    four_days_ago = int(time.time()) - (4 * 86400)
    old_storage_key = f"extracted/test_old_unused_{uuid.uuid4().hex[:6]}.png"

    # Create dummy storage file
    storage_service.put_bytes(old_storage_key, b"fake_png_data", "image/png")

    old_artifact = Artifact(
        id=str(uuid.uuid4()),
        project_id=project.id,
        type="image",
        storage_key=old_storage_key,
        created_at=four_days_ago,
    )
    db_session.add(old_artifact)
    db_session.commit()
    old_art_id = old_artifact.id

    # Run cleaner policy with 3 days retention
    report = DataCleanerService.run_cleanup_policy(db_session, retention_days=3, dry_run=False)

    assert report["unused_images_deleted"] >= 1
    assert old_storage_key in report["deleted_storage_keys"]

    # Verify DB record is deleted
    remaining = db_session.scalar(select(Artifact).where(Artifact.id == old_art_id))
    assert remaining is None

    # Verify storage file is removed
    with pytest.raises((FileNotFoundError, Exception)):
        storage_service.get_bytes(old_storage_key)


def test_cleaner_preserves_used_old_images(db_session: Session):
    """Verify that images older than 3 days that ARE used in a deck are strictly PRESERVED."""
    user, project = create_test_user_and_project(db_session, "Active Project")

    four_days_ago = int(time.time()) - (4 * 86400)
    used_key = f"extracted/used_old_{uuid.uuid4().hex[:6]}.png"
    storage_service.put_bytes(used_key, b"active_deck_image_data", "image/png")

    used_art_id = f"art_preserved_{uuid.uuid4().hex[:6]}"
    used_artifact = Artifact(
        id=used_art_id,
        project_id=project.id,
        type="image",
        storage_key=used_key,
        created_at=four_days_ago,
    )
    db_session.add(used_artifact)

    # Reference in a deck_json artifact
    deck_spec = {
        "slides": [
            {"slideId": "s1", "headline": "Ancient Coins", "imageArtifactId": used_art_id}
        ]
    }
    deck_json = Artifact(
        id=str(uuid.uuid4()),
        project_id=project.id,
        type="deck_json",
        json_data=json.dumps(deck_spec),
        created_at=four_days_ago,
    )
    db_session.add(deck_json)
    db_session.commit()

    report = DataCleanerService.run_cleanup_policy(db_session, retention_days=3, dry_run=False)

    # Check used image was preserved
    assert report["used_images_preserved"] >= 1
    assert used_key not in report["deleted_storage_keys"]

    # Verify DB record and file still exist
    rem_art = db_session.scalar(select(Artifact).where(Artifact.id == used_art_id))
    assert rem_art is not None
    assert storage_service.get_bytes(used_key) == b"active_deck_image_data"

    # Clean up test file
    storage_service.delete_object(used_key)


def test_cleaner_preserves_fresh_unused_images(db_session: Session):
    """Verify that unused images newer than 3 days are PRESERVED (retention window)."""
    user, project = create_test_user_and_project(db_session, "Fresh Project")

    # 1 day ago (within 3 day window)
    one_day_ago = int(time.time()) - (1 * 86400)
    fresh_key = f"extracted/fresh_img_{uuid.uuid4().hex[:6]}.png"
    storage_service.put_bytes(fresh_key, b"fresh_image_data", "image/png")

    fresh_art_id = str(uuid.uuid4())
    fresh_artifact = Artifact(
        id=fresh_art_id,
        project_id=project.id,
        type="image",
        storage_key=fresh_key,
        created_at=one_day_ago,
    )
    db_session.add(fresh_artifact)
    db_session.commit()

    report = DataCleanerService.run_cleanup_policy(db_session, retention_days=3, dry_run=False)

    assert fresh_key not in report["deleted_storage_keys"]

    # Verify DB record and file still exist
    rem_art = db_session.scalar(select(Artifact).where(Artifact.id == fresh_art_id))
    assert rem_art is not None
    assert storage_service.get_bytes(fresh_key) == b"fresh_image_data"

    # Clean up test file
    storage_service.delete_object(fresh_key)


def test_cleaner_dry_run_mode(db_session: Session):
    """Verify that dry_run=True simulates deletions without altering DB or storage."""
    user, project = create_test_user_and_project(db_session, "Dry Run Project")

    five_days_ago = int(time.time()) - (5 * 86400)
    dry_key = f"extracted/dry_run_img_{uuid.uuid4().hex[:6]}.png"
    storage_service.put_bytes(dry_key, b"dry_run_bytes", "image/png")

    dry_art_id = str(uuid.uuid4())
    dry_art = Artifact(
        id=dry_art_id,
        project_id=project.id,
        type="image",
        storage_key=dry_key,
        created_at=five_days_ago,
    )
    db_session.add(dry_art)
    db_session.commit()

    # Dry run
    report = DataCleanerService.run_cleanup_policy(db_session, retention_days=3, dry_run=True)

    assert report["dry_run"] is True
    assert report["unused_images_deleted"] >= 1
    assert dry_key in report["deleted_storage_keys"]

    # In dry run, DB row and file MUST NOT be deleted!
    assert db_session.scalar(select(Artifact).where(Artifact.id == dry_art_id)) is not None
    assert storage_service.get_bytes(dry_key) == b"dry_run_bytes"

    # Clean up test file
    storage_service.delete_object(dry_key)


def test_admin_cleaner_api_endpoints(client, admin_auth_headers):
    """Verify admin endpoints for checking status and running the DataCleaner policy."""
    # 1. GET status
    status_resp = client.get("/api/v1/admin/storage/cleaner/status", headers=admin_auth_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["success"] is True
    assert status_data["policy"]["retention_days"] == 3
    assert status_data["policy"]["enabled"] is True

    # 2. POST run in dry-run mode
    run_resp = client.post(
        "/api/v1/admin/storage/cleaner/run?retention_days=3&dry_run=true",
        headers=admin_auth_headers,
    )
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["success"] is True
    assert run_data["report"]["dry_run"] is True
    assert run_data["report"]["retention_days"] == 3
