"""ExperientialLabs Free Model Discovery, Quality Sequencer, and Cooldown Tracker."""

import logging
import time
from typing import Any, ClassVar

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Curated free models for ExperientialLabs based on verified working models and promotional tiers
CURATED_EXPERIENTIALLABS_FREE_MODELS: list[dict[str, Any]] = [
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "context_length": 128000,
        "description": "Fast, high-quality multimodal reasoning engine",
    },
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "context_length": 128000,
        "description": "Flagship multimodal intelligence engine",
    },
    {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra (Free)",
        "context_length": 1050000,
        "description": "Experiential Cloud frontier multi-modal reasoning engine (Free tier)",
    },
    {
        "id": "claude-fable-5.1",
        "name": "Claude Fable 5.1 (Free)",
        "context_length": 1000000,
        "description": "Experiential Cloud Claude Fable reasoning model (Free tier)",
    },
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna (Free)",
        "context_length": 1050000,
        "description": "Experiential Cloud GPT-5.6 high-throughput model (Free tier)",
    },
    {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash (Free)",
        "context_length": 1050000,
        "description": "Ultra-fast DeepSeek V4 presentation layout engine (Free tier)",
    },
    {
        "id": "qwen3.8-27b",
        "name": "Qwen3.8 27B (Free)",
        "context_length": 1000000,
        "description": "Qwen 3.8 27B instruction & presentation design model (Free tier)",
    },
    {
        "id": "nemotron-3-ultra-550b-a55b-free",
        "name": "NVIDIA Nemotron 3 Ultra 550B (Free)",
        "context_length": 1000000,
        "description": "550B flagship reasoning and instruction model",
    },
    {
        "id": "minimax-m3-free",
        "name": "MiniMax M3 (Free)",
        "context_length": 1048576,
        "description": "1M context high-throughput generation model",
    },
    {
        "id": "gemma-4-26b-a4b-it-free",
        "name": "Google Gemma 4 26B (Free)",
        "context_length": 262144,
        "description": "Google Gemma 4 instruction model",
    },
    {
        "id": "openrouter-free",
        "name": "ExperientialLabs Universal Free Router",
        "context_length": 200000,
        "description": "Dynamic gateway across available free models",
    },
]


class ExperientialLabsModelManager:
    """Manages dynamic discovery, ranking, and health state for ExperientialLabs free models."""

    _models_cache: ClassVar[list[dict[str, Any]]] = []
    _last_fetched: float = 0.0
    _cache_ttl_seconds: float = 3600.0  # 1 hour cache

    # Cooldown tracking: model_id -> timestamp until which model is on cooldown
    _cooldowns: ClassVar[dict[str, float]] = {}
    _failure_counts: ClassVar[dict[str, int]] = {}
    _success_counts: ClassVar[dict[str, int]] = {}

    @classmethod
    def calculate_quality_score(cls, model: dict[str, Any]) -> int:
        """Calculate quality score (higher = better quality, tried first)."""
        model_id = model.get("id", "").lower()
        name = model.get("name", "").lower()
        combined = f"{model_id} {name}"

        # 1. Verified working models
        if model_id == "gpt-4o-mini" or "gpt-4o-mini" in combined:
            return 100
        if model_id == "gpt-4o" or "gpt-4o" in combined:
            return 99

        # 2. Universal dynamic free router
        if model_id in {"openrouter-free", "openrouter/free"}:
            return 80

        # 3. Promotional frontier tiers
        if "gpt-6-astra" in combined:
            return 75
        if "claude-fable-5.1" in combined or "claude-fable-5" in combined:
            return 74
        if "gpt-5.6-luna" in combined:
            return 73
        if "deepseek-v4-flash" in combined:
            return 72
        if "qwen3.8-27b" in combined:
            return 71

        score = 0
        ctx = int(model.get("context_length") or 0)

        # 3. Provider pedigree
        if model_id in ("gpt-4o-mini", "gpt-4o"):
            score += 60
        elif any(p in combined for p in ("anthropic", "claude")):
            score += 35
        elif any(p in combined for p in ("openai", "gpt")):
            score += 30
        elif any(p in combined for p in ("deepseek", "qwen")):
            score += 25
        elif any(p in combined for p in ("google", "gemini", "meta", "llama")):
            score += 20
        else:
            score += 15

        # 4. Capability keywords
        if any(w in combined for w in ("flash", "fast", "lightning")):
            score += 25
        elif any(w in combined for w in ("reasoning", "r1", "cot")):
            score += 20
        elif any(w in combined for w in ("pro", "coder")):
            score += 15

        # Exclude or downrank pure safety classifiers
        if "content-safety" in combined or "guard" in combined:
            score -= 50

        # 5. Context window
        if ctx >= 1000000:
            score += 20
        elif ctx >= 500000:
            score += 15
        elif ctx >= 250000:
            score += 10
        elif ctx >= 128000:
            score += 5

        return max(score, 1)

    @classmethod
    async def fetch_free_models(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch all free models from ExperientialLabs or return cached ranking."""
        now = time.time()
        if not force_refresh and cls._models_cache and (now - cls._last_fetched < cls._cache_ttl_seconds):
            return cls._models_cache

        effective_key = api_key or settings.effective_experientiallabs_api_key
        effective_base = (base_url or settings.experientiallabs_base_url or "https://api.experientiallabs.ai/v1").rstrip("/")

        free_models: list[dict[str, Any]] = []

        if effective_key:
            try:
                url = f"{effective_base}/models"
                headers = {"Authorization": f"Bearer {effective_key}"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        promotional_ids = {
                            "gpt-4o-mini",
                            "gpt-4o",
                            "qwen3.8-27b",
                            "deepseek-v4-flash",
                            "gpt-5.6-luna",
                            "claude-fable-5.1",
                            "gpt-6-astra",
                        }
                        for m in data:
                            mid = m.get("id", "")
                            mid_lower = mid.lower()
                            is_free = (
                                mid_lower in promotional_ids
                                or "-free" in mid_lower
                                or ":free" in mid_lower
                                or mid_lower == "openrouter-free"
                            )
                            if is_free:
                                free_models.append({
                                    "id": mid,
                                    "name": m.get("name", mid),
                                    "context_length": m.get("context_length", 1000000),
                                    "description": m.get("description", f"ExperientialLabs {mid} free tier"),
                                })
            except Exception:
                logger.warning("ExperientialLabs free model discovery failed; using curated fallback", exc_info=True)

        if not free_models:
            free_models = list(CURATED_EXPERIENTIALLABS_FREE_MODELS)

        for m in free_models:
            m["quality_score"] = cls.calculate_quality_score(m)

        free_models.sort(key=lambda m: m["quality_score"], reverse=True)

        cls._models_cache = free_models
        cls._last_fetched = now
        return cls._models_cache

    @classmethod
    def mark_model_failure(cls, model_id: str, status_code: int | None = None, cooldown_seconds: int = 60) -> None:
        """Mark a model failure and trigger temporary cooldown to skip it during cascade."""
        now = time.time()
        cls._failure_counts[model_id] = cls._failure_counts.get(model_id, 0) + 1

        if status_code in (429, 400, 403) and cooldown_seconds < 300:
            cooldown_seconds = 3600

        factor = min(cls._failure_counts[model_id], 4)
        actual_cooldown = cooldown_seconds * factor
        cls._cooldowns[model_id] = now + actual_cooldown
        logger.warning(
            "ExperientialLabs model %s failed (HTTP %s); cooldown=%ss",
            model_id,
            status_code,
            actual_cooldown,
        )

    @classmethod
    def mark_model_success(cls, model_id: str) -> None:
        """Record a successful response and clear failure count."""
        cls._failure_counts[model_id] = 0
        cls._cooldowns.pop(model_id, None)
        cls._success_counts[model_id] = cls._success_counts.get(model_id, 0) + 1

    @classmethod
    def is_model_available(cls, model_id: str) -> bool:
        """Check whether a model is currently available or in cooldown."""
        now = time.time()
        cooldown_until = cls._cooldowns.get(model_id, 0.0)
        return now >= cooldown_until

    @classmethod
    async def get_ranked_candidates(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return the list of available free models in priority sequence (high quality first)."""
        all_models = await cls.fetch_free_models(api_key=api_key, base_url=base_url, force_refresh=force_refresh)

        available = [m for m in all_models if cls.is_model_available(m["id"])]
        in_cooldown = [m for m in all_models if not cls.is_model_available(m["id"])]

        return available if available else in_cooldown

    @classmethod
    def get_status_overview(cls) -> list[dict[str, Any]]:
        """Return diagnostic overview of all models, their quality score, and cooldown status."""
        now = time.time()
        models = cls._models_cache or CURATED_EXPERIENTIALLABS_FREE_MODELS
        result = []
        for m in models:
            mid = m["id"]
            cooldown_until = cls._cooldowns.get(mid, 0.0)
            remaining_cooldown = max(0, int(cooldown_until - now))
            result.append({
                "id": mid,
                "name": m.get("name", mid),
                "quality_score": m.get("quality_score", cls.calculate_quality_score(m)),
                "context_length": m.get("context_length", 0),
                "is_available": remaining_cooldown == 0,
                "cooldown_remaining_seconds": remaining_cooldown,
                "failures": cls._failure_counts.get(mid, 0),
                "successes": cls._success_counts.get(mid, 0),
            })
        result.sort(key=lambda x: x["quality_score"], reverse=True)
        return result
