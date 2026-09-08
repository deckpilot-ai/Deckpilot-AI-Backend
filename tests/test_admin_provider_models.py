"""Tests for Admin AI Provider configuration, model fetching, and model priority routing."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import httpx

from app.core.security import hash_password
from app.models.provider import AIProvider, AIProviderModel
from app.models.user import User
from app.services.provider_router import ProviderRouter


def get_admin_token(client: TestClient, db: Session) -> str:
    admin = db.query(User).filter(User.email == "admin@deckpilot.ai").first()
    if not admin:
        admin = User(
            email="admin@deckpilot.ai",
            password_hash=hash_password("adminpass123"),
            role="admin",
            status="active",
        )
        db.add(admin)
        db.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@deckpilot.ai", "password": "adminpass123"},
    )
    assert resp.status_code == 200
    return resp.json()["token"]


def test_admin_provider_crud_and_models(client: TestClient, db_session: Session):
    token = get_admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a custom AI provider with base_url, api_key, and priority
    create_resp = client.post(
        "/api/v1/admin/providers",
        headers=headers,
        json={
            "name": "deepseek-custom",
            "base_url": "https://api.deepseek.com/v1",
            "provider_type": "openai_compatible",
            "priority": 50,
            "api_key": "sk-deepseek-secret-key-12345",
            "key_label": "production-key",
            "models": [
                {"model_id": "deepseek-chat", "display_name": "DeepSeek Chat V3", "priority": 90, "enabled": 1},
                {"model_id": "deepseek-reasoner", "display_name": "DeepSeek R1", "priority": 95, "enabled": 1},
            ],
        },
    )
    assert create_resp.status_code == 201
    prov_id = create_resp.json()["id"]

    # 2. List providers and verify keys + models are returned
    list_resp = client.get("/api/v1/admin/providers", headers=headers)
    assert list_resp.status_code == 200
    providers = list_resp.json()
    custom_prov = next((p for p in providers if p["id"] == prov_id), None)
    assert custom_prov is not None
    assert custom_prov["name"] == "deepseek-custom"
    assert custom_prov["base_url"] == "https://api.deepseek.com/v1"
    assert custom_prov["priority"] == 50
    assert len(custom_prov["keys"]) == 1
    assert custom_prov["keys"][0]["label"] == "production-key"
    assert len(custom_prov["models"]) == 2
    # Verify models sorted by priority descending (95, then 90)
    assert custom_prov["models"][0]["model_id"] == "deepseek-reasoner"
    assert custom_prov["models"][0]["priority"] == 95
    assert custom_prov["models"][1]["model_id"] == "deepseek-chat"
    assert custom_prov["models"][1]["priority"] == 90

    # 3. Update provider details (change priority and base_url)
    update_resp = client.put(
        f"/api/v1/admin/providers/{prov_id}",
        headers=headers,
        json={"priority": 85, "base_url": "https://api.deepseek.com/v1"},
    )
    assert update_resp.status_code == 200

    # 4. Mock remote model fetching
    mock_models_response = {
        "data": [
            {"id": "deepseek-coder", "name": "DeepSeek Coder 33B", "context_length": 65536},
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "context_length": 128000},
        ]
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = httpx.Response(200, json=mock_models_response, request=httpx.Request("GET", "https://api.deepseek.com/v1/models"))
        mock_get.return_value = mock_resp

        fetch_resp = client.post(
            "/api/v1/admin/providers/fetch-models",
            headers=headers,
            json={"provider_id": prov_id},
        )
        assert fetch_resp.status_code == 200
        fetch_data = fetch_resp.json()
        assert fetch_data["total"] == 2
        assert any(m["id"] == "deepseek-coder" for m in fetch_data["models"])

    # 5. Update individual model priority
    reasoner_model_id = custom_prov["models"][0]["id"]
    put_model_resp = client.put(
        f"/api/v1/admin/providers/{prov_id}/models/{reasoner_model_id}",
        headers=headers,
        json={"priority": 99, "enabled": 1},
    )
    assert put_model_resp.status_code == 200
    assert put_model_resp.json()["priority"] == 99

    # 6. Delete a model
    chat_model_id = custom_prov["models"][1]["id"]
    del_model_resp = client.delete(
        f"/api/v1/admin/providers/{prov_id}/models/{chat_model_id}",
        headers=headers,
    )
    assert del_model_resp.status_code == 204

    # 7. Verify remaining models
    get_models_resp = client.get(f"/api/v1/admin/providers/{prov_id}/models", headers=headers)
    assert get_models_resp.status_code == 200
    remaining = get_models_resp.json()
    assert len(remaining) == 1
    assert remaining[0]["model_id"] == "deepseek-reasoner"
    assert remaining[0]["priority"] == 99

    # 8. Delete provider
    del_prov_resp = client.delete(f"/api/v1/admin/providers/{prov_id}", headers=headers)
    assert del_prov_resp.status_code == 204


@pytest.mark.asyncio
async def test_llm_priority_routing_cascade(db_session: Session):
    # Setup two providers: Provider A (priority 80) and Provider B (priority 20)
    prov_a = ProviderRouter.register_provider(
        db=db_session,
        name="provider-alpha",
        base_url="https://api.alpha.ai/v1",
        priority=80,
    )
    ProviderRouter.add_key(db=db_session, provider_id=prov_a.id, label="alpha-key", secret="sk-alpha-test-secret")
    ProviderRouter.save_provider_models(
        db=db_session,
        provider_id=prov_a.id,
        models_data=[
            {"model_id": "alpha-model-top", "priority": 90, "enabled": 1},
            {"model_id": "alpha-model-backup", "priority": 50, "enabled": 1},
        ],
    )

    # Call LLM with mock: when top model fails, backup model is tried and succeeds
    call_records = []

    async def mock_post(url, headers, json, *args, **kwargs):
        model = json.get("model")
        call_records.append(model)
        if model == "alpha-model-top":
            # Simulate 500 error on top model
            return httpx.Response(500, text="Internal Server Error", request=httpx.Request("POST", url))
        elif model == "alpha-model-backup":
            # Backup succeeds
            resp_body = {
                "choices": [{"message": {"content": '{"plan": "Generated by Alpha Backup"}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
            return httpx.Response(200, json=resp_body, request=httpx.Request("POST", url))
        return httpx.Response(404, text="Not Found", request=httpx.Request("POST", url))

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await ProviderRouter.call_llm(
            db=db_session,
            agent_type="deck_planner",
            system_prompt="You are a deck planner",
            user_prompt="Create a slide deck about AI",
            response_schema={"type": "object"},
        )

    # Verify that alpha-model-top was tried FIRST (priority 90), and alpha-model-backup was tried SECOND (priority 50)
    assert call_records[0] == "alpha-model-top"
    assert call_records[1] == "alpha-model-backup"
    assert result == {"plan": "Generated by Alpha Backup"}
