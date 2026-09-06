"""OpenRouter Free Model Discovery, Quality Sequencer, and Cooldown Tracker."""

import logging
import time
from typing import Any, ClassVar

import httpx

logger = logging.getLogger(__name__)

# Curated fallback list used when offline or initial cold start
CURATED_FREE_MODELS: list[dict[str, Any]] = [
    {
        "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "name": "NVIDIA: Nemotron 3 Ultra (free)",
        "context_length": 1000000,
        "description": "550B flagship reasoning and instruction model",
    },
    {
        "id": "nvidia/nemotron-3-super-120b-a12b:free",
        "name": "NVIDIA: Nemotron 3 Super (free)",
        "context_length": 262144,
        "description": "120B high-capacity presentation planning model",
    },
    {
        "id": "google/gemma-4-31b-it:free",
        "name": "Google: Gemma 4 31B (free)",
        "context_length": 262144,
        "description": "Google frontier dense instruction tuned model",
    },
    {
        "id": "google/gemma-4-26b-a4b-it:free",
        "name": "Google: Gemma 4 26B A4B (free)",
        "context_length": 262144,
        "description": "Google Gemma 4 architecture",
    },
    {
        "id": "minimax/minimax-m3:free",
        "name": "MiniMax: MiniMax M3 (free)",
        "context_length": 1048576,
        "description": "1M context high-throughput generation model",
    },
    {
        "id": "z-ai/glm-5.2:free",
        "name": "Z.ai: GLM 5.2 (free)",
        "context_length": 256000,
        "description": "Bilingual enterprise reasoning model",
    },
    {
        "id": "nvidia/nemotron-3.5-lightning:free",
        "name": "NVIDIA: Nemotron 3.5 Lightning (free)",
        "context_length": 1000000,
        "description": "High-speed 1M context layout engine",
    },
    {
        "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "name": "NVIDIA: Nemotron 3 Nano Omni (free)",
        "context_length": 256000,
        "description": "Multi-modal reasoning model",
    },
    {
        "id": "openrouter/free",
        "name": "OpenRouter Free Router",
        "context_length": 200000,
        "description": "Universal dynamic router across available free models",
    },
]


class OpenRouterModelManager:
    """Manages dynamic discovery, ranking, and health state for OpenRouter free models."""

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
        score = 0
        model_id = model.get("id", "").lower()
        name = model.get("name", "").lower()
        ctx = int(model.get("context_length") or 0)
        combined = f"{model_id} {name}"

        # 1. Parameter scale heuristic (0-40 pts)
        if any(w in combined for w in ("550b", "500b", "ultra")):
            score += 35
        elif any(w in combined for w in ("120b", "70b", "72b", "super")):
            score += 38
        elif any(w in combined for w in ("32b", "31b", "30b", "26b", "27b")):
            score += 32
        elif any(w in combined for w in ("14b", "8b", "7b")):
            score += 25
        elif any(w in combined for w in ("2b", "3b", "nano")):
            score += 10
        else:
            score += 20

        # 2. Capability & Speed keywords (0-30 pts)
        if any(w in combined for w in ("lightning", "flash", "fast")):
            score += 25  # High-throughput models prevent 80-second queue hangs
        elif any(w in combined for w in ("reasoning", "r1", "cot")):
            score += 20
        elif any(w in combined for w in ("pro", "coder")):
            score += 18

        # Exclude or downrank pure safety classifiers
        if "content-safety" in combined or "guard" in combined:
            score -= 50

        # 3. Context window capacity (0-20 pts)
        if ctx >= 1000000:
            score += 20
        elif ctx >= 500000:
            score += 15
        elif ctx >= 250000:
            score += 10
        elif ctx >= 128000:
            score += 5

        # 4. Leading proven model families
        if "nemotron-3.5-lightning" in combined:
            score += 20
        elif "nemotron" in combined:
            score += 12
        if "gemma-4" in combined or "gemini" in combined:
            score += 15
        if "minimax" in combined:
            score += 10
        if "glm-5" in combined:
            score += 10

        # 5. Universal router fallback baseline
        if model_id == "openrouter/free":
            return 100  # Always #1: dynamically routes to lowest-latency free model

        return max(score, 1)

    @classmethod
    async def fetch_free_models(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Fetch all free models from OpenRouter or return cached ranking."""
        now = time.time()
        if not force_refresh and cls._models_cache and (now - cls._last_fetched < cls._cache_ttl_seconds):
            return cls._models_cache

        free_models: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={
                        "HTTP-Referer": "https://deckpilot.ai",
                        "X-Title": "deckpilotAI",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for m in data:
                        mid = m.get("id", "")
                        pricing = m.get("pricing", {})
                        p_prompt = str(pricing.get("prompt", "")).strip()
                        p_comp = str(pricing.get("completion", "")).strip()

                        is_free = (
                            ":free" in mid
                            or mid == "openrouter/free"
                            or (p_prompt in ("0", "0.0") and p_comp in ("0", "0.0"))
                        )

                        output_modalities = m.get("architecture", {}).get("output_modalities", ["text"])
                        if is_free and "text" in output_modalities:
                            free_models.append({
                                "id": mid,
                                "name": m.get("name", mid),
                                "context_length": m.get("context_length", 32768),
                                "description": m.get("description", ""),
                                "pricing": pricing,
                            })
        except Exception:
            logger.warning("OpenRouter model discovery failed; using curated fallback", exc_info=True)

        # If fetch failed or yielded 0 models, use curated fallback list
        if not free_models:
            free_models = list(CURATED_FREE_MODELS)

        # Rank all free models by quality score descending
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

        # Exponential backoff based on consecutive failures
        factor = min(cls._failure_counts[model_id], 4)
        actual_cooldown = cooldown_seconds * factor
        cls._cooldowns[model_id] = now + actual_cooldown
        logger.warning(
            "OpenRouter model %s failed (HTTP %s); cooldown=%ss",
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
    async def get_ranked_candidates(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Return the list of available free models in priority sequence (high quality first)."""
        all_models = await cls.fetch_free_models(force_refresh=force_refresh)

        # Separate into available (non-cooldown) and in-cooldown models
        available = [m for m in all_models if cls.is_model_available(m["id"])]
        in_cooldown = [m for m in all_models if not cls.is_model_available(m["id"])]

        # Try available models first; if all are on cooldown, still attempt in-cooldown as last resort
        return available if available else in_cooldown

    @classmethod
    def get_status_overview(cls) -> list[dict[str, Any]]:
        """Return diagnostic overview of all models, their quality score, and cooldown status."""
        now = time.time()
        models = cls._models_cache or CURATED_FREE_MODELS
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
