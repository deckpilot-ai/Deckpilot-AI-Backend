"""Tests for OpenRouter free models discovery, quality sequencing, and cascade fallback."""

import json as json_lib
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.provider import AIKey, AIProvider
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.services.openrouter_models import OpenRouterModelManager
from app.services.provider_router import ProviderRouter


def test_quality_score_calculation():
    """Verify that high-parameter, reasoning models score significantly higher."""
    ultra_model = {
        "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "name": "NVIDIA: Nemotron 3 Ultra (free)",
        "context_length": 1000000,
    }
    small_model = {
        "id": "liquid/lfm-2.5-2.6b:free",
        "name": "LiquidAI: LFM2.5-2.6B (free)",
        "context_length": 65536,
    }
    safety_model = {
        "id": "nvidia/nemotron-3.5-content-safety:free",
        "name": "NVIDIA: Nemotron 3.5 Content Safety (free)",
        "context_length": 128000,
    }

    score_ultra = OpenRouterModelManager.calculate_quality_score(ultra_model)
    score_small = OpenRouterModelManager.calculate_quality_score(small_model)
    score_safety = OpenRouterModelManager.calculate_quality_score(safety_model)

    assert score_ultra > score_small, f"Expected ultra {score_ultra} > small {score_small}"
    assert score_small > score_safety, f"Expected small {score_small} > safety {score_safety}"


@pytest.mark.asyncio
async def test_fetch_free_models_and_ranking():
    """Verify free models are fetched, scored, and sorted descending."""
    models = await OpenRouterModelManager.fetch_free_models(force_refresh=True)
    assert len(models) > 0

    # Ensure all models are sorted descending by quality score
    scores = [m["quality_score"] for m in models]
    assert scores == sorted(scores, reverse=True)

    # Top model should be a high quality model
    top_model = models[0]
    assert top_model["quality_score"] >= 60


def test_model_cooldown_and_availability():
    """Verify failure triggers cooldown and success clears it."""
    test_model = "test-provider/test-model:free"
    assert OpenRouterModelManager.is_model_available(test_model)

    # Mark failure
    OpenRouterModelManager.mark_model_failure(test_model, status_code=429, cooldown_seconds=60)
    assert not OpenRouterModelManager.is_model_available(test_model)

    # Mark success
    OpenRouterModelManager.mark_model_success(test_model)
    assert OpenRouterModelManager.is_model_available(test_model)


@pytest.mark.asyncio
async def test_cascade_fallback_with_context_handover(db_session):
    """
    Test that when Model 1 returns 429 rate limit,
    the exact context is automatically passed to Model 2.
    """
    # 1. Register OpenRouter provider with test key
    provider = ProviderRouter.register_provider(
        db=db_session,
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        priority=10,
    )
    ProviderRouter.add_key(db_session, provider.id, "test-key", "sk-or-v1-testkey123")

    call_history = []

    async def mock_post(url, headers, **kwargs):
        payload = kwargs.get("json", {})
        model_called = payload.get("model")
        messages_called = payload.get("messages")
        call_history.append({"model": model_called, "messages": messages_called})

        mock_resp = MagicMock()
        # Model 1 fails with 429
        if len(call_history) == 1:
            mock_resp.status_code = 429
            mock_resp.json.return_value = {"error": "Rate limit exceeded"}
        else:
            # Model 2 succeeds with valid JSON
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": json_lib.dumps({
                                "deckTitle": "Cascaded Presentation",
                                "slides": [{"slideId": "s01", "message": "Success from fallback"}],
                            })
                        }
                    }
                ]
            }
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await ProviderRouter.call_llm(
            db=db_session,
            agent_type="deck_planner",
            system_prompt="You are Deck Planner.",
            user_prompt="Build 5 slides on renewable energy.",
            response_schema={"type": "object"},
        )

    # Verify that at least 2 models were called sequentially
    assert len(call_history) >= 2
    first_model = call_history[0]["model"]
    second_model = call_history[1]["model"]
    assert first_model != second_model

    # Verify exact context preservation
    assert call_history[0]["messages"] == call_history[1]["messages"]
    assert call_history[1]["messages"][1]["content"] == "Build 5 slides on renewable energy."

    # Verify result came from the succeeding model
    assert result.get("deckTitle") == "Cascaded Presentation"


def test_sync_environment_providers(db_session):
    """Verify that keys from settings automatically sync into database tables."""
    original_key = settings.openrouter_api_key
    try:
        settings.openrouter_api_key = "sk-or-env-auto-sync-key-456"
        ProviderRouter.sync_environment_providers(db_session)

        provider = db_session.scalar(select(AIProvider).where(AIProvider.name == "openrouter"))
        assert provider is not None
        assert provider.base_url == "https://openrouter.ai/api/v1"

        keys = db_session.scalars(select(AIKey).where(AIKey.provider_id == provider.id)).all()
        assert len(keys) >= 1
    finally:
        settings.openrouter_api_key = original_key


def test_admin_free_models_endpoints(client, db_session):
    """Verify admin endpoints for listing free models and checking provider status."""
    # Create an admin user
    admin_user = AuthService.register(
        db=db_session,
        req=RegisterRequest(
            email="admin_tester@deckpilot.ai",
            password="secureadminpass123",
        ),
    )
    admin_user.role = "admin"
    db_session.commit()
    _, token = AuthService.login(
        db_session,
        LoginRequest(email="admin_tester@deckpilot.ai", password="secureadminpass123"),
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get free models sequence
    resp = client.get("/api/v1/admin/providers/free-models", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert data["total"] > 0
    assert "quality_score" in data["models"][0]

    # 2. Get high level provider status
    status_resp = client.get("/api/v1/admin/providers/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "providers" in status_data
    assert "available_free_models_count" in status_data

    # 3. Refresh free models
    refresh_resp = client.post("/api/v1/admin/providers/free-models/refresh", headers=headers)
    assert refresh_resp.status_code == 200
    assert "Successfully refreshed" in refresh_resp.json()["message"]
