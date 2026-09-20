"""Tests for Google OAuth login and registration endpoints."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core.config import settings
from app.services.auth_service import AuthService


def test_auth_providers_endpoint(client: TestClient):
    resp = client.get("/api/v1/auth/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "google" in data
    assert isinstance(data["google"]["enabled"], bool)


def test_google_auth_new_user_success(client: TestClient):
    mock_payload = {
        "email": "newgoogleuser@example.com",
        "name": "Google Explorer",
        "picture": "https://example.com/avatar.jpg",
        "sub": "google-uid-12345",
        "email_verified": "true",
        "aud": "mock-client-id",
    }

    with patch.object(AuthService, "verify_google_credential", return_value=mock_payload):
        resp = client.post(
            "/api/v1/auth/google",
            json={"credential": "mock-valid-id-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "newgoogleuser@example.com"
        assert data["user"]["role"] == "user"
        assert "deckpilotai_token" in resp.cookies

        # Verify profile via /me
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "newgoogleuser@example.com"


def test_google_auth_existing_user_login(client: TestClient):
    # First, register an existing user with standard email/password
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "existingpilot@deckpilot.ai", "password": "SecurePassword123!"},
    )
    assert reg_resp.status_code == 201

    # Now login with Google using the same email
    mock_payload = {
        "email": "existingpilot@deckpilot.ai",
        "name": "Existing Pilot",
        "sub": "google-uid-67890",
        "email_verified": "true",
    }

    with patch.object(AuthService, "verify_google_credential", return_value=mock_payload):
        resp = client.post(
            "/api/v1/auth/google",
            json={"credential": "mock-existing-user-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "existingpilot@deckpilot.ai"
        assert "token" in data


def test_google_auth_invalid_credential_fails(client: TestClient):
    with patch.object(AuthService, "verify_google_credential", side_effect=ValueError("Invalid Google credential")):
        resp = client.post(
            "/api/v1/auth/google",
            json={"credential": "invalid-token-credential-xyz"},
        )
        assert resp.status_code == 400
        assert "Invalid Google credential" in resp.json()["detail"]


def test_google_auth_missing_credential_validation(client: TestClient):
    resp = client.post(
        "/api/v1/auth/google",
        json={"credential": ""},
    )
    assert resp.status_code == 422
