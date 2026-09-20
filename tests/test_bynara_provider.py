"""Tests for Bynara AI provider configuration, free models, and router integration."""

from unittest.mock import patch
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.provider import AIKey, AIProvider, AIProviderModel
from app.services.provider_router import ProviderRouter


def test_bynara_sync_environment_providers(db_session: Session):
    """Verify Bynara provider and its curated free models are synchronized into the DB."""
    # Ensure sync runs
    ProviderRouter.sync_environment_providers(db_session)

    provider = db_session.scalar(select(AIProvider).where(AIProvider.name == "bynara"))
    assert provider is not None
    assert provider.base_url == "https://router.bynara.id/v1"
    assert provider.enabled == 1
    assert provider.priority == 27

    # Check key exists
    keys = db_session.scalars(select(AIKey).where(AIKey.provider_id == provider.id)).all()
    assert len(keys) >= 1
    active_key, secret = ProviderRouter.select_active_key(db_session, provider.id)
    assert active_key is not None
    assert secret == settings.bynara_api_key

    # Check models - ONLY free models must be configured
    models = db_session.scalars(
        select(AIProviderModel).where(AIProviderModel.provider_id == provider.id)
    ).all()
    model_ids = {m.model_id for m in models}

    expected_free_models = {
        "ling-3.0-flash-vl-free",
        "ling-3.0-flash-fin-free",
        "nemotron-3.5-lightning-free",
        "nemotron-3-ultra-free",
        "ling-3.0-flash-sante-free",
        "nemotron-3-super-free",
        "nex-n2.5-pro",
        "laguna-s-2.1",
    }
    assert model_ids == expected_free_models
    for m in models:
        assert m.enabled == 1
        assert m.priority > 0

    # Ensure paid models like agnes-2.5-flash and stepfun-3.7-flash are NOT present
    assert "agnes-2.5-flash" not in model_ids
    assert "stepfun-3.7-flash" not in model_ids


def test_bynara_fetch_models_filters_to_free(db_session: Session):
    """Verify fetch_provider_models for Bynara filters out paid models."""
    import asyncio

    mock_response_data = {
        "data": [
            {"id": "agnes-2.5-flash", "name": "Agnes 2.5 Flash"},
            {"id": "stepfun-3.7-flash", "name": "Stepfun 3.7 Flash"},
            {"id": "ling-3.0-flash-vl-free", "name": "Ling 3.0 Flash VL Free"},
            {"id": "nemotron-3-ultra-free", "name": "Nemotron 3 Ultra Free"},
        ]
    }

    async def _run():
        async def mock_get(url, *args, **kwargs):
            return httpx.Response(200, json=mock_response_data, request=httpx.Request("GET", url))

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            discovered = await ProviderRouter.fetch_provider_models(
                base_url="https://router.bynara.id/v1",
                api_key=settings.bynara_api_key,
            )

        discovered_ids = {m["id"] for m in discovered}
        assert "agnes-2.5-flash" not in discovered_ids
        assert "stepfun-3.7-flash" not in discovered_ids
        assert "ling-3.0-flash-vl-free" in discovered_ids
        assert "nemotron-3-ultra-free" in discovered_ids

    asyncio.run(_run())
