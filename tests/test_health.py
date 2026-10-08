from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["service"] == "deckpilotAI-backend"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "database": "connected"}


def test_cors_allowed_custom_domains(client: TestClient) -> None:
    for origin in ("https://deckpilotai.com", "https://www.deckpilotai.com"):
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin

        get_res = client.get("/api/v1/health", headers={"Origin": origin})
        assert get_res.status_code == 200
        assert get_res.headers.get("access-control-allow-origin") == origin


def test_cors_disallowed_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://unauthorized-domain.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
