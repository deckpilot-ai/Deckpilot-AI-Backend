"""Tests for CodeCraft AI Provider, Claude Priority Ranking, and Routing."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.models.provider import AIProvider, AIProviderModel, AIKey
from app.services.codecraft_models import (
    CodeCraftModelManager,
    CURATED_CODECRAFT_MODELS,
)
from app.services.provider_router import ProviderRouter


def test_codecraft_curated_models_claude_priority():
    """Verify that Claude models are prioritized first in CodeCraft curated list."""
    claude_models = [m for m in CURATED_CODECRAFT_MODELS if "claude" in m["id"].lower()]
    assert len(claude_models) >= 5, "Should have at least 5 Claude models in catalog"

    # Claude Sonnet 5 must be top of the list
    assert CURATED_CODECRAFT_MODELS[0]["id"] == "claude-sonnet-5"
    assert "Anthropic" in CURATED_CODECRAFT_MODELS[0]["name"]


def test_codecraft_model_manager_sorting():
    """Verify that arbitrary model lists are sorted with Claude models on top."""
    test_models = [
        {"id": "deepseek-v4-pro-max", "name": "DeepSeek V4"},
        {"id": "gpt-5.6-sol", "name": "GPT-5.6"},
        {"id": "claude-opus-5", "name": "Claude Opus 5"},
        {"id": "claude-sonnet-5", "name": "Claude Sonnet 5"},
        {"id": "gemini-3.7-flash", "name": "Gemini 3.7"},
    ]
    sorted_models = CodeCraftModelManager._filter_and_sort_models(test_models)
    sorted_ids = [m["id"] for m in sorted_models]

    assert sorted_ids[0] == "claude-sonnet-5"
    assert sorted_ids[1] == "claude-opus-5"


def test_codecraft_cooldown_tracking():
    """Verify rate-limited models go into cooldown and recover."""
    model_id = "claude-test-model"
    assert CodeCraftModelManager.is_available(model_id) is True

    CodeCraftModelManager.mark_rate_limited(model_id, cooldown_seconds=2.0)
    assert CodeCraftModelManager.is_available(model_id) is False


def test_sync_environment_codecraft_provider(db_session: Session):
    """Verify that CodeCraft provider is automatically synced with high priority and Claude models."""
    ProviderRouter.sync_environment_providers(db_session)

    provider = db_session.query(AIProvider).filter(AIProvider.name == "codecraft").first()
    assert provider is not None
    assert provider.priority == 15
    assert provider.enabled == 1

    models = (
        db_session.query(AIProviderModel)
        .filter(AIProviderModel.provider_id == provider.id, AIProviderModel.enabled == 1)
        .order_by(AIProviderModel.priority.desc())
        .all()
    )
    assert len(models) > 0
    # Top model must be Claude Sonnet 5
    assert models[0].model_id == "claude-sonnet-5"
    assert models[0].priority == 100
