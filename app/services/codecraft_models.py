"""CodeCraft Model Discovery, Quality Sequencer, and Priority Router.

Prioritizes Anthropic Claude models (Claude Sonnet 5, Claude Opus 5, etc.) as highest priority,
followed by other top frontier models (GPT-5.6, Gemini 3.7, DeepSeek V4, Grok 4.6, Qwen 3.8).
"""

import logging
import time
from typing import Any, ClassVar

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Curated CodeCraft models list with Claude models as highest priority
CURATED_CODECRAFT_MODELS: list[dict[str, Any]] = [
    {
        "id": "claude-sonnet-5",
        "name": "Claude Sonnet 5 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Sonnet 5 - Flagship balance of high intelligence, reasoning, and speed",
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Opus 5 - Maximum intelligence and complex slide structuring",
    },
    {
        "id": "claude-opus-4.8",
        "name": "Claude Opus 4.8 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Opus 4.8 - Advanced reasoning and design architecture",
    },
    {
        "id": "claude-opus-4.7",
        "name": "Claude Opus 4.7 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Opus 4.7 - Deep analytical generation",
    },
    {
        "id": "claude-opus-4.6",
        "name": "Claude Opus 4.6 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Opus 4.6 - High capability generation",
    },
    {
        "id": "claude-fable-5",
        "name": "Claude Fable 5 (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Fable 5 - Creative narrative and deck copywriting",
    },
    {
        "id": "claude-mythos-preview",
        "name": "Claude Mythos Preview (Anthropic)",
        "context_length": 200000,
        "description": "Anthropic Claude Mythos Preview - Next-generation experimental reasoning",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol (OpenAI)",
        "context_length": 256000,
        "description": "OpenAI GPT-5.6 Sol - Ultra-high performance multi-modal engine",
    },
    {
        "id": "gpt-5.5-pro",
        "name": "GPT-5.5 Pro (OpenAI)",
        "context_length": 256000,
        "description": "OpenAI GPT-5.5 Pro - Enterprise grade reasoning and formatting",
    },
    {
        "id": "gemini-3.7-flash",
        "name": "Gemini 3.7 Flash (Google)",
        "context_length": 1000000,
        "description": "Google Gemini 3.7 Flash - 1M context ultra-fast presentation generation",
    },
    {
        "id": "deepseek-v4-pro-max",
        "name": "DeepSeek V4 Pro Max",
        "context_length": 128000,
        "description": "DeepSeek V4 Pro Max - Advanced code and structured presentation synthesis",
    },
    {
        "id": "grok-4.6",
        "name": "Grok 4.6 (xAI)",
        "context_length": 256000,
        "description": "xAI Grok 4.6 - High-speed real-time reasoning engine",
    },
    {
        "id": "qwen3.8-max",
        "name": "Qwen 3.8 Max",
        "context_length": 128000,
        "description": "Alibaba Qwen 3.8 Max - Bilingual presentation and outline structuring",
    },
    {
        "id": "kimi-k3",
        "name": "Kimi K3 (Moonshot)",
        "context_length": 256000,
        "description": "Moonshot Kimi K3 - Long-context research and document analysis",
    },
    {
        "id": "glm-5.3",
        "name": "GLM 5.3 (Zhipu)",
        "context_length": 128000,
        "description": "Zhipu GLM 5.3 - Multi-turn reasoning engine",
    },
    {
        "id": "seed-2.1-pro",
        "name": "Seed 2.1 Pro",
        "context_length": 128000,
        "description": "ByteDance Seed 2.1 Pro - High quality layout generation",
    },
]


class CodeCraftModelManager:
    """Manages CodeCraft API dynamic model discovery, health status, and prioritizes Claude models."""

    _cached_models: ClassVar[list[dict[str, Any]]] = []
    _cache_timestamp: ClassVar[float] = 0.0
    _CACHE_TTL_SECONDS: ClassVar[float] = 3600.0  # 1 hour
    _model_cooldowns: ClassVar[dict[str, float]] = {}
    _COOLDOWN_SECONDS: ClassVar[float] = 60.0

    @classmethod
    def get_effective_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return prioritized list of CodeCraft models with Claude models at the highest priority."""
        now = time.time()

        if not force_refresh and cls._cached_models and (now - cls._cache_timestamp) < cls._CACHE_TTL_SECONDS:
            return cls._filter_and_sort_models(cls._cached_models)

        resolved_base_url = (base_url or settings.codecraft_base_url or "https://codecraftapi.com/v1").rstrip("/")
        resolved_key = (api_key or settings.codecraft_api_key or "").strip()

        if not resolved_key:
            return cls._filter_and_sort_models(CURATED_CODECRAFT_MODELS)

        try:
            url = f"{resolved_base_url}/models"
            headers = {
                "Authorization": f"Bearer {resolved_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_models = data.get("data", [])
                    discovered = cls._parse_models_response(raw_models)
                    if discovered:
                        cls._cached_models = discovered
                        cls._cache_timestamp = now
                        logger.info("Successfully fetched %d models from CodeCraft API", len(discovered))
                        return cls._filter_and_sort_models(discovered)
                else:
                    logger.warning("CodeCraft models endpoint returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("Failed to fetch live CodeCraft models: %s", e)

        if not cls._cached_models:
            cls._cached_models = CURATED_CODECRAFT_MODELS
            cls._cache_timestamp = now

        return cls._filter_and_sort_models(cls._cached_models)

    @classmethod
    def _parse_models_response(cls, raw_models: list[Any]) -> list[dict[str, Any]]:
        """Parse raw /models API response."""
        parsed: list[dict[str, Any]] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id") or item.get("name")
            if not model_id or not isinstance(model_id, str):
                continue

            # Check if we have curated metadata
            curated_match = next((c for c in CURATED_CODECRAFT_MODELS if c["id"] == model_id), None)

            if curated_match:
                parsed.append({
                    "id": model_id,
                    "name": curated_match["name"],
                    "context_length": item.get("context_length") or curated_match.get("context_length", 128000),
                    "description": curated_match.get("description", f"CodeCraft Model: {model_id}"),
                })
            else:
                display_name = model_id.replace("-", " ").replace("_", " ").title()
                parsed.append({
                    "id": model_id,
                    "name": display_name,
                    "context_length": item.get("context_length", 128000),
                    "description": f"CodeCraft Model: {model_id}",
                })
        return parsed

    @classmethod
    def _filter_and_sort_models(cls, models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort models ensuring Claude models have the highest priority."""
        def model_sort_key(m: dict[str, Any]) -> tuple[int, int]:
            mid = m["id"].lower()
            # Tier 1: Claude models (Top priority)
            if "claude" in mid:
                if "sonnet" in mid:
                    return (0, 0)
                if "opus-5" in mid:
                    return (0, 1)
                if "opus-4.8" in mid:
                    return (0, 2)
                if "opus-4.7" in mid:
                    return (0, 3)
                if "opus-4.6" in mid:
                    return (0, 4)
                if "fable" in mid:
                    return (0, 5)
                if "mythos" in mid:
                    return (0, 6)
                return (0, 10)
            # Tier 2: GPT-5.6 / GPT-5.5
            if "gpt-5" in mid:
                return (1, 0)
            # Tier 3: Gemini 3.7 / 3.6
            if "gemini" in mid:
                return (2, 0)
            # Tier 4: DeepSeek V4
            if "deepseek" in mid:
                return (3, 0)
            # Tier 5: Grok
            if "grok" in mid:
                return (4, 0)
            # Tier 6: Qwen
            if "qwen" in mid:
                return (5, 0)
            # Tier 7: Others
            return (6, 0)

        sorted_models = sorted(models, key=model_sort_key)
        return sorted_models

    @classmethod
    def mark_rate_limited(cls, model_id: str, cooldown_seconds: float | None = None) -> None:
        """Mark a model as temporarily rate-limited or degraded."""
        cd = cooldown_seconds or cls._COOLDOWN_SECONDS
        cls._model_cooldowns[model_id] = time.time() + cd
        logger.warning("CodeCraft model %s placed in cooldown for %.1fs", model_id, cd)

    @classmethod
    def is_available(cls, model_id: str) -> bool:
        """Check if a model is currently outside of its cooldown period."""
        expiry = cls._model_cooldowns.get(model_id, 0)
        return time.time() >= expiry
