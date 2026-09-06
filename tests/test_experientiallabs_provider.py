"""Tests for ExperientialLabs free models discovery, quality sequencing, and cascade fallback."""

import json as json_lib
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.provider import AIKey, AIProvider
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.services.experientiallabs_models import ExperientialLabsModelManager
from app.services.provider_router import ProviderRouter


def test_experientiallabs_quality_score_calculation():
    """Verify promotional 5 free models and high-parameter models score highest."""
    astra_model = {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra (Free)",
        "context_length": 1050000,
    }
    fable_model = {
        "id": "claude-fable-5.1",
        "name": "Claude Fable 5.1 (Free)",
        "context_length": 1000000,
    }
    qwen_model = {
        "id": "qwen3.8-27b",
        "name": "Qwen3.8 27B (Free)",
        "context_length": 1000000,
    }
    safety_model = {
        "id": "nemotron-3.5-content-safety-free",
        "name": "NVIDIA Nemotron Content Safety",
        "context_length": 128000,
    }

    score_astra = ExperientialLabsModelManager.calculate_quality_score(astra_model)
    score_fable = ExperientialLabsModelManager.calculate_quality_score(fable_model)
    score_qwen = ExperientialLabsModelManager.calculate_quality_score(qwen_model)
    score_safety = ExperientialLabsModelManager.calculate_quality_score(safety_model)

    assert score_astra >= score_fable
    assert score_fable >= score_qwen
    assert score_qwen > score_safety, f"Expected qwen {score_qwen} > safety {score_safety}"


@pytest.mark.asyncio
async def test_experientiallabs_fetch_free_models_and_ranking():
    """Verify ExperientialLabs free models are fetched, scored, and sorted descending."""
    models = await ExperientialLabsModelManager.fetch_free_models(force_refresh=True)
    assert len(models) >= 5

    # Check promotional 5 models are present
    model_ids = {m["id"] for m in models}
    expected_promotional = {
        "gpt-6-astra",
        "claude-fable-5.1",
        "gpt-5.6-luna",
        "deepseek-v4-flash",
        "qwen3.8-27b",
    }
    assert expected_promotional.issubset(model_ids)

    # Ensure all models are sorted descending by quality score
    scores = [m["quality_score"] for m in models]
    assert scores == sorted(scores, reverse=True)


def test_experientiallabs_model_cooldown_and_availability():
    """Verify failure triggers cooldown and success clears it."""
    test_model = "test-provider/test-free-model"
    assert ExperientialLabsModelManager.is_model_available(test_model)

    ExperientialLabsModelManager.mark_model_failure(test_model, status_code=429, cooldown_seconds=60)
    assert not ExperientialLabsModelManager.is_model_available(test_model)

    ExperientialLabsModelManager.mark_model_success(test_model)
    assert ExperientialLabsModelManager.is_model_available(test_model)


@pytest.mark.asyncio
async def test_experientiallabs_cascade_fallback_with_context_handover(db_session):
    """
    Test that when ExperientialLabs Model 1 returns HTTP 429 rate limit or quota error,
    the exact context is automatically passed to Model 2.
    """
    provider = ProviderRouter.register_provider(
        db=db_session,
        name="experientiallabs",
        base_url="https://api.experientiallabs.ai/v1",
        priority=11,
    )
    ProviderRouter.add_key(db_session, provider.id, "explabs-test-key", "xpl_test_key_12345678")

    call_history = []

    async def mock_post(url, headers, **kwargs):
        payload = kwargs.get("json", {})
        model_called = payload.get("model")
        messages_called = payload.get("messages")
        call_history.append({"url": url, "model": model_called, "messages": messages_called})

        mock_resp = MagicMock()
        # Model 1 fails with 429
        if len(call_history) == 1:
            mock_resp.status_code = 429
            mock_resp.json.return_value = {"error": {"message": "Rate limit / quota", "type": "insufficient_quota"}}
        else:
            # Model 2 succeeds with valid JSON
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": json_lib.dumps({
                                "deckTitle": "ExperientialLabs Presentation",
                                "slides": [{"slideId": "s01", "message": "Success from ExperientialLabs cascade"}],
                            })
                        }
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 120},
            }
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await ProviderRouter.call_llm(
            db=db_session,
            agent_type="deck_planner",
            system_prompt="You are Deck Planner.",
            user_prompt="Build 5 slides on AI innovation.",
            response_schema={"type": "object"},
        )

    assert len(call_history) >= 2
    first_model = call_history[0]["model"]
    second_model = call_history[1]["model"]
    assert first_model != second_model

    # Verify exact context preservation
    assert call_history[0]["messages"] == call_history[1]["messages"]
    assert call_history[1]["messages"][1]["content"] == "Build 5 slides on AI innovation."

    # Verify result came from the succeeding model
    assert result.get("deckTitle") == "ExperientialLabs Presentation"


def test_sync_environment_experientiallabs_provider(db_session):
    """Verify that ExperientialLabs key from settings automatically syncs into database."""
    original_key = settings.experientiallabs_api_key
    try:
        settings.experientiallabs_api_key = "xpl_test_auto_sync_key_98765"
        ProviderRouter.sync_environment_providers(db_session)

        provider = db_session.scalar(select(AIProvider).where(AIProvider.name == "experientiallabs"))
        assert provider is not None
        assert provider.base_url == "https://api.experientiallabs.ai/v1"

        keys = db_session.scalars(select(AIKey).where(AIKey.provider_id == provider.id)).all()
        assert len(keys) >= 1
    finally:
        settings.experientiallabs_api_key = original_key


def test_admin_experientiallabs_endpoints(client, db_session):
    """Verify admin endpoints for listing ExperientialLabs free models and checking provider status."""
    admin_user = AuthService.register(
        db=db_session,
        req=RegisterRequest(
            email="explabs_admin@deckpilot.ai",
            password="secureadminpass123",
        ),
    )
    admin_user.role = "admin"
    db_session.commit()
    _, token = AuthService.login(
        db_session,
        LoginRequest(email="explabs_admin@deckpilot.ai", password="secureadminpass123"),
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get ExperientialLabs free models sequence
    resp = client.get("/api/v1/admin/providers/free-models?provider=experientiallabs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert data["total"] >= 5
    model_ids = [m["id"] for m in data["models"]]
    assert "gpt-6-astra" in model_ids
    assert "qwen3.8-27b" in model_ids

    # 2. Get high level provider status
    status_resp = client.get("/api/v1/admin/providers/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "experientiallabs_cascade_active" in status_data
    assert "available_free_models_count" in status_data

    # 3. Refresh ExperientialLabs free models
    refresh_resp = client.post("/api/v1/admin/providers/free-models/refresh?provider=experientiallabs", headers=headers)
    assert refresh_resp.status_code == 200
    assert "Successfully refreshed ExperientialLabs" in refresh_resp.json()["message"]
