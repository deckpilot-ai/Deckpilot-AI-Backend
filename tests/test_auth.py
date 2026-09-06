"""Tests for authentication endpoints."""

from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient):
    # 1. Register new user
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "pilot@deckpilot.ai", "password": "securepassword123"},
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "pilot@deckpilot.ai"
    assert user_data["role"] == "user"
    assert "id" in user_data

    # 2. Duplicate registration fails
    dup_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "pilot@deckpilot.ai", "password": "securepassword123"},
    )
    assert dup_resp.status_code == 409

    # 3. Login with correct credentials
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "pilot@deckpilot.ai", "password": "securepassword123"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data
    token = login_data["token"]
    assert "deckpilotai_token" in login_resp.cookies

    # 4. Get current user profile via Bearer token
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "pilot@deckpilot.ai"

    # 5. Get current user profile via cookie
    me_cookie_resp = client.get("/api/v1/auth/me")
    assert me_cookie_resp.status_code == 200
    assert me_cookie_resp.json()["email"] == "pilot@deckpilot.ai"

    # 6. Logout
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200

    # Revoked bearer tokens must stop working, not only browser cookies.
    revoked_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoked_resp.status_code == 401

    # 7. Unauthenticated access fails
    fail_resp = client.get("/api/v1/auth/me")
    assert fail_resp.status_code == 401


def test_registration_cannot_self_assign_admin(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "password": "securepassword123",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_repeated_login_creates_distinct_revocable_sessions(client: TestClient):
    credentials = {"email": "repeat-login@example.com", "password": "strongpassword123"}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201

    first = client.post("/api/v1/auth/login", json=credentials)
    second = client.post("/api/v1/auth/login", json=credentials)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["token"] != second.json()["token"]


def test_login_rate_limit(client: TestClient):
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "incorrect"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "incorrect"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
