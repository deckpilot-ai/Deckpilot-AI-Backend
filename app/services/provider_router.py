"""AI Provider Router, Key Security, and Dynamic Model Priority Routing Engine."""

import json
import logging
import re
import time
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import (
    decrypt_secret,
    encrypt_secret,
    is_legacy_encrypted_secret,
)
from app.core.network_security import validate_provider_base_url
from app.models.audit import UsageEvent
from app.models.provider import AgentRoute, AIKey, AIProvider, AIProviderModel
from app.services.codecraft_models import (
    CURATED_CODECRAFT_MODELS,
    CodeCraftModelManager,
)
from app.services.diagnostics_service import DiagnosticsService
from app.services.experientiallabs_models import ExperientialLabsModelManager
from app.services.health_tracker import health_tracker
from app.services.openrouter_models import OpenRouterModelManager

logger = logging.getLogger(__name__)


def _parse_llm_response(content: str, response_schema: Any | None) -> dict[str, Any]:
    """Robustly parse LLM output, extracting JSON from markdown code blocks or raw text if needed."""
    if not response_schema:
        return {"text": content.strip()}

    cleaned = content.strip()
    # Try direct parse first
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Extract JSON inside ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # Extract first {...} or [...]
    obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", content)
    if obj_match:
        try:
            res = json.loads(obj_match.group(1).strip())
            return res if isinstance(res, dict) else {"data": res}
        except Exception:
            pass

    # If all JSON parsing attempts fail, return text wrapped in dict
    return {"text": cleaned}


class ProviderRouter:
    @staticmethod
    def sync_environment_providers(db: Session) -> None:
        """Auto-synchronize system AI providers and API keys from settings / environment into database."""
        provider_configs = [
            ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", settings.gemini_api_key, 18),
            ("codecraft", settings.codecraft_base_url or "https://codecraftapi.com/v1", settings.codecraft_api_key, 15),
            ("experientiallabs", settings.experientiallabs_base_url or "https://api.experientiallabs.ai/v1", settings.effective_experientiallabs_api_key, 11),
            ("openrouter", "https://openrouter.ai/api/v1", settings.openrouter_api_key, 10),
            ("openai", "https://api.openai.com/v1", settings.openai_api_key, 8),
            ("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, 7),
            ("mistral", "https://api.mistral.ai/v1", settings.mistral_api_key, 6),
            ("anthropic", "https://api.anthropic.com/v1", settings.anthropic_api_key, 5),
        ]

        for name, base_url, key_secret, priority in provider_configs:
            try:
                provider = db.scalar(select(AIProvider).where(AIProvider.name == name))
                if not provider:
                    provider = AIProvider(
                        name=name,
                        base_url=base_url,
                        provider_type="openai_compatible",
                        priority=priority,
                        enabled=1,
                    )
                    db.add(provider)
                    db.commit()
                    db.refresh(provider)
                else:
                    if provider.priority != priority:
                        provider.priority = priority
                        db.commit()

                # Seed initial default models if this provider has none configured
                existing_models = db.scalars(select(AIProviderModel).where(AIProviderModel.provider_id == provider.id)).all()
                if not existing_models:
                    default_models = []
                    if name == "gemini":
                        default_models = [
                            {"model_id": "gemini-3.8-flash", "display_name": "Gemini 3.8 Flash", "priority": 100, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-3.7-flash", "display_name": "Gemini 3.7 Flash", "priority": 98, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-3.5-flash", "display_name": "Gemini 3.5 Flash", "priority": 96, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "priority": 94, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-3.5-flash-lite", "display_name": "Gemini 3.5 Flash Lite", "priority": 92, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-2.5-flash-lite", "display_name": "Gemini 2.5 Flash Lite", "priority": 90, "enabled": 1, "context_length": 1000000},
                            {"model_id": "gemini-3.1-flash-lite-preview", "display_name": "Gemini 3.1 Flash Lite Preview", "priority": 88, "enabled": 1, "context_length": 1000000},
                        ]
                    elif name == "codecraft":
                        default_models = [
                            {"model_id": m["id"], "display_name": m["name"], "priority": max(100 - (i * 2), 1), "enabled": 1, "context_length": m.get("context_length")}
                            for i, m in enumerate(CURATED_CODECRAFT_MODELS)
                        ]
                    elif name == "openrouter":
                        from app.services.openrouter_models import CURATED_FREE_MODELS
                        default_models = [
                            {"model_id": m["id"], "display_name": m["name"], "priority": 100 - (i * 5), "enabled": 1, "context_length": m.get("context_length")}
                            for i, m in enumerate(CURATED_FREE_MODELS[:10])
                        ]
                    elif name == "experientiallabs":
                        from app.services.experientiallabs_models import CURATED_EXPERIENTIALLABS_FREE_MODELS
                        default_models = [
                            {"model_id": m["id"], "display_name": m["name"], "priority": 100 - (i * 5), "enabled": 1, "context_length": m.get("context_length")}
                            for i, m in enumerate(CURATED_EXPERIENTIALLABS_FREE_MODELS[:10])
                        ]
                    elif name == "openai":
                        default_models = [
                            {"model_id": "gpt-4o", "display_name": "GPT-4o (Flagship)", "priority": 95, "enabled": 1, "context_length": 128000},
                            {"model_id": "gpt-4o-mini", "display_name": "GPT-4o Mini", "priority": 90, "enabled": 1, "context_length": 128000},
                        ]
                    elif name == "groq":
                        default_models = [
                            {"model_id": "llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B (Versatile)", "priority": 90, "enabled": 1, "context_length": 128000},
                        ]

                    if default_models:
                        ProviderRouter.save_provider_models(db, provider.id, default_models)

                # Sync environment key if configured
                if key_secret and key_secret.strip():
                    existing_keys = db.scalars(select(AIKey).where(AIKey.provider_id == provider.id)).all()
                    has_matching_key = False
                    for k in existing_keys:
                        try:
                            if decrypt_secret(k.encrypted_secret) == key_secret.strip():
                                if is_legacy_encrypted_secret(k.encrypted_secret):
                                    k.encrypted_secret = encrypt_secret(key_secret.strip())
                                    db.commit()
                                has_matching_key = True
                                break
                        except Exception:
                            logger.warning("Unable to decrypt stored key %s for provider %s", k.id, name, exc_info=True)
                            continue

                    if not has_matching_key:
                        encrypted = encrypt_secret(key_secret.strip())
                        new_key = AIKey(
                            provider_id=provider.id,
                            label=f"{name}-env-key",
                            encrypted_secret=encrypted,
                            enabled=1,
                        )
                        db.add(new_key)
                        db.commit()
            except Exception:
                db.rollback()
                logger.warning("Error synchronizing provider %s", name, exc_info=True)

    @staticmethod
    def register_provider(
        db: Session,
        name: str,
        base_url: str,
        provider_type: str = "openai_compatible",
        priority: int = 1,
    ) -> AIProvider:
        base_url = validate_provider_base_url(base_url)
        existing = db.scalar(select(AIProvider).where(AIProvider.name == name))
        if existing:
            existing.base_url = base_url
            existing.provider_type = provider_type
            existing.priority = priority
            db.commit()
            db.refresh(existing)
            return existing

        provider = AIProvider(
            name=name,
            base_url=base_url,
            provider_type=provider_type,
            priority=priority,
            enabled=1,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)
        return provider

    @staticmethod
    def update_provider(
        db: Session,
        provider_id: str,
        name: str | None = None,
        base_url: str | None = None,
        provider_type: str | None = None,
        priority: int | None = None,
        enabled: int | None = None,
    ) -> AIProvider:
        provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
        if not provider:
            raise ValueError("Provider not found")
        if name is not None and name.strip():
            # Check unique constraint if name changes
            if name.strip() != provider.name:
                conflict = db.scalar(select(AIProvider).where(AIProvider.name == name.strip()))
                if conflict:
                    raise ValueError(f"Provider with name '{name.strip()}' already exists")
                provider.name = name.strip()
        if base_url is not None and base_url.strip():
            provider.base_url = validate_provider_base_url(base_url.strip())
        if provider_type is not None and provider_type.strip():
            provider.provider_type = provider_type.strip()
        if priority is not None:
            provider.priority = int(priority)
        if enabled is not None:
            provider.enabled = 1 if enabled in (1, True, "1") else 0

        db.commit()
        db.refresh(provider)
        return provider

    @staticmethod
    def delete_provider(db: Session, provider_id: str) -> None:
        provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
        if provider:
            db.delete(provider)
            db.commit()

    @staticmethod
    def add_key(
        db: Session,
        provider_id: str,
        label: str,
        secret: str,
    ) -> AIKey:
        normalized_secret = secret.strip()
        if len(normalized_secret) < 8:
            raise ValueError("Provider secret must contain at least 8 non-whitespace characters")
        encrypted = encrypt_secret(normalized_secret)
        key = AIKey(
            provider_id=provider_id,
            label=label,
            encrypted_secret=encrypted,
            enabled=1,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return key

    @staticmethod
    def rotate_key(db: Session, key: AIKey, secret: str, label: str | None = None) -> AIKey:
        normalized_secret = secret.strip()
        if len(normalized_secret) < 8:
            raise ValueError("Provider secret must contain at least 8 non-whitespace characters")
        key.encrypted_secret = encrypt_secret(normalized_secret)
        if label is not None:
            key.label = label
        key.enabled = 1
        key.cooldown_until = None
        key.failure_count = 0
        db.commit()
        db.refresh(key)
        return key

    @staticmethod
    def revoke_key(db: Session, key: AIKey) -> None:
        key.enabled = 0
        key.cooldown_until = None
        db.commit()

    @staticmethod
    def set_agent_route(
        db: Session,
        agent_type: str,
        candidates: list[dict[str, Any]],
    ) -> AgentRoute:
        route = db.scalar(select(AgentRoute).where(AgentRoute.agent_type == agent_type))
        if not route:
            route = AgentRoute(agent_type=agent_type, route_json=json.dumps(candidates))
            db.add(route)
        else:
            route.route_json = json.dumps(candidates)
        db.commit()
        db.refresh(route)
        return route

    @staticmethod
    def select_active_key(db: Session, provider_id: str) -> tuple[AIKey, str] | None:
        now = int(time.time())
        stmt = (
            select(AIKey)
            .where(
                AIKey.provider_id == provider_id,
                AIKey.enabled == 1,
                (AIKey.cooldown_until == None) | (AIKey.cooldown_until <= now),
            )
            .order_by(AIKey.failure_count.asc(), AIKey.last_used_at.asc())
        )
        key = db.scalar(stmt)
        if not key:
            return None
        decrypted = decrypt_secret(key.encrypted_secret)
        if is_legacy_encrypted_secret(key.encrypted_secret):
            key.encrypted_secret = encrypt_secret(decrypted)
            db.commit()
        return key, decrypted

    @staticmethod
    async def fetch_provider_models(
        base_url: str,
        api_key: str | None = None,
        provider_type: str = "openai_compatible",
    ) -> list[dict[str, Any]]:
        """Fetch available models dynamically from any OpenAI-compatible or standard AI provider endpoint."""
        cleaned_url = base_url.strip().rstrip("/")
        if cleaned_url.endswith("/chat/completions"):
            cleaned_url = cleaned_url[:-len("/chat/completions")].rstrip("/")

        candidate_urls = [f"{cleaned_url}/models"]
        if not cleaned_url.endswith("/v1"):
            candidate_urls.append(f"{cleaned_url}/v1/models")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://deckpilot.ai",
            "X-Title": "deckpilotAI",
        }
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        last_error = "Unable to connect to models endpoint"
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
            for url in candidate_urls:
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        models_raw = []
                        if isinstance(data, dict):
                            if "data" in data and isinstance(data["data"], list):
                                models_raw = data["data"]
                            elif "models" in data and isinstance(data["models"], list):
                                models_raw = data["models"]
                            elif "items" in data and isinstance(data["items"], list):
                                models_raw = data["items"]
                        elif isinstance(data, list):
                            models_raw = data

                        discovered: list[dict[str, Any]] = []
                        for idx, item in enumerate(models_raw):
                            if isinstance(item, str):
                                m_id = item.strip()
                                discovered.append({
                                    "id": m_id,
                                    "name": m_id,
                                    "context_length": None,
                                    "description": None,
                                    "default_priority": max(100 - (idx * 5), 1),
                                })
                            elif isinstance(item, dict) and "id" in item:
                                m_id = str(item["id"]).strip()
                                name = str(item.get("name") or m_id)
                                ctx = item.get("context_length") or item.get("context_window") or item.get("max_tokens")
                                desc_str = item.get("description")
                                discovered.append({
                                    "id": m_id,
                                    "name": name,
                                    "context_length": int(ctx) if ctx and str(ctx).isdigit() else None,
                                    "description": str(desc_str) if desc_str else None,
                                    "default_priority": max(100 - (idx * 5), 1),
                                })
                        if discovered:
                            return discovered
                    else:
                        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as err:
                    last_error = str(err)

        # Fallback to curated catalog for known providers if live endpoint is unreachable
        if "codecraft" in cleaned_url:
            effective = CodeCraftModelManager.get_effective_models(api_key=api_key, base_url=cleaned_url)
            return [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "context_length": m.get("context_length"),
                    "description": m.get("description"),
                    "default_priority": max(100 - (idx * 2), 1),
                }
                for idx, m in enumerate(effective)
            ]
        elif "openrouter" in cleaned_url:
            from app.services.openrouter_models import CURATED_FREE_MODELS
            return [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "context_length": m.get("context_length"),
                    "description": m.get("description"),
                    "default_priority": max(100 - (idx * 5), 1),
                }
                for idx, m in enumerate(CURATED_FREE_MODELS)
            ]
        elif "experientiallabs" in cleaned_url:
            from app.services.experientiallabs_models import CURATED_EXPERIENTIALLABS_FREE_MODELS
            return [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "context_length": m.get("context_length"),
                    "description": m.get("description"),
                    "default_priority": max(100 - (idx * 5), 1),
                }
                for idx, m in enumerate(CURATED_EXPERIENTIALLABS_FREE_MODELS)
            ]
        elif "anthropic" in cleaned_url:
            return [
                {"id": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "context_length": 200000, "description": "Anthropic hybrid reasoning model", "default_priority": 95},
                {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "context_length": 200000, "description": "Anthropic flagship model", "default_priority": 90},
                {"id": "claude-3-5-haiku", "name": "Claude 3.5 Haiku", "context_length": 200000, "description": "Fast lightweight model", "default_priority": 85},
            ]
        elif "openai" in cleaned_url:
            return [
                {"id": "gpt-4o", "name": "GPT-4o (Flagship)", "context_length": 128000, "description": "Flagship multimodal intelligence engine", "default_priority": 95},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000, "description": "Fast high-quality multimodal reasoning engine", "default_priority": 90},
                {"id": "o3-mini", "name": "o3 Mini", "context_length": 200000, "description": "STEM reasoning model", "default_priority": 85},
            ]

        raise ValueError(f"Failed to fetch models: {last_error}")

    @staticmethod
    def save_provider_models(
        db: Session,
        provider_id: str,
        models_data: list[dict[str, Any]],
    ) -> list[AIProviderModel]:
        """Upsert models and their priorities for a provider."""
        provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
        if not provider:
            raise ValueError("Provider not found")

        saved_models: list[AIProviderModel] = []
        for item in models_data:
            model_id = str(item.get("model_id") or item.get("id") or "").strip()
            if not model_id:
                continue
            priority = int(item.get("priority", 1))
            enabled = 1 if item.get("enabled", True) in (True, 1, "1") else 0
            display_name = item.get("display_name") or item.get("name")
            ctx_len = item.get("context_length")

            existing = db.scalar(
                select(AIProviderModel).where(
                    AIProviderModel.provider_id == provider_id,
                    AIProviderModel.model_id == model_id,
                )
            )
            if existing:
                existing.priority = priority
                existing.enabled = enabled
                if display_name:
                    existing.display_name = str(display_name)
                if ctx_len is not None:
                    existing.context_length = int(ctx_len) if str(ctx_len).isdigit() else None
                saved_models.append(existing)
            else:
                new_model = AIProviderModel(
                    provider_id=provider_id,
                    model_id=model_id,
                    display_name=str(display_name) if display_name else None,
                    priority=priority,
                    enabled=enabled,
                    context_length=int(ctx_len) if ctx_len and str(ctx_len).isdigit() else None,
                )
                db.add(new_model)
                saved_models.append(new_model)

        db.commit()
        for m in saved_models:
            db.refresh(m)
        return saved_models

    @staticmethod
    def update_provider_model(
        db: Session,
        model_db_id: str,
        priority: int | None = None,
        enabled: int | None = None,
        display_name: str | None = None,
    ) -> AIProviderModel:
        model = db.scalar(select(AIProviderModel).where(AIProviderModel.id == model_db_id))
        if not model:
            raise ValueError("Model configuration not found")
        if priority is not None:
            model.priority = int(priority)
        if enabled is not None:
            model.enabled = 1 if enabled in (1, True, "1") else 0
        if display_name is not None:
            model.display_name = display_name
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def delete_provider_model(db: Session, model_db_id: str) -> None:
        model = db.scalar(select(AIProviderModel).where(AIProviderModel.id == model_db_id))
        if model:
            db.delete(model)
            db.commit()

    @staticmethod
    async def call_llm(
        db: Session,
        agent_type: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
        user_id: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes an LLM call using adaptive health-aware routing.

        Instead of static priority order, candidates are scored by a composite
        of base priority (30%), EWMA latency (40%), and reliability (30%).
        Circuit-broken candidates are skipped automatically.
        """
        now = int(time.time())

        # 1. Get all enabled providers (env sync is done once at startup)
        providers = db.scalars(
            select(AIProvider)
            .where(AIProvider.enabled == 1)
            .order_by(desc(AIProvider.priority))
        ).all()

        # 2. Build a flat list of all (provider, model, key) candidates
        all_candidates: list[dict[str, Any]] = []

        for provider in providers:
            try:
                provider_base_url = validate_provider_base_url(provider.base_url)
            except ValueError:
                logger.error("Disabled unsafe provider URL for provider %s (%s)", provider.name, provider.id)
                provider.enabled = 0
                db.commit()
                continue

            active_key_tuple = ProviderRouter.select_active_key(db, provider.id)
            if not active_key_tuple:
                continue
            key_record, secret_key = active_key_tuple

            # Determine candidate model IDs
            configured_models = db.scalars(
                select(AIProviderModel)
                .where(AIProviderModel.provider_id == provider.id, AIProviderModel.enabled == 1)
                .order_by(desc(AIProviderModel.priority))
            ).all()

            model_candidates: list[tuple[str, int]] = []  # (model_id, base_priority)
            if configured_models:
                model_candidates = [(m.model_id, m.priority) for m in configured_models]
            elif provider.name == "codecraft":
                effective = CodeCraftModelManager.get_effective_models(
                    api_key=secret_key, base_url=provider_base_url
                )
                model_candidates = [
                    (m["id"], max(100 - (i * 2), 1))
                    for i, m in enumerate(effective)
                    if CodeCraftModelManager.is_available(m["id"])
                ]
            elif provider.name == "experientiallabs":
                ranked = await ExperientialLabsModelManager.get_ranked_candidates(
                    api_key=secret_key, base_url=provider_base_url
                )
                model_candidates = [(m["id"], max(100 - (i * 5), 1)) for i, m in enumerate(ranked[:5])]
            elif provider.name == "openrouter":
                ranked = await OpenRouterModelManager.get_ranked_candidates()
                model_candidates = [(m["id"], max(100 - (i * 5), 1)) for i, m in enumerate(ranked[:4])]
            else:
                p_name = provider.name.lower()
                if "groq" in p_name:
                    model_candidates = [("openai/gpt-oss-120b", 90), ("llama-3.3-70b-versatile", 80)]
                elif "gemini" in p_name:
                    model_candidates = [
                        (settings.gemini_model or "gemini-3.8-flash", 100),
                        ("gemini-3.7-flash", 98),
                        ("gemini-3.5-flash", 96),
                        ("gemini-2.5-flash", 94),
                        ("gemini-3.5-flash-lite", 92),
                        ("gemini-2.5-flash-lite", 90),
                    ]
                elif "openai" in p_name:
                    model_candidates = [("gpt-4o-mini", 90), ("gpt-4o", 95)]
                elif "mistral" in p_name:
                    model_candidates = [("mistral-small-latest", 85), ("mistral-large-latest", 90)]
                else:
                    model_candidates = [("default", 50)]

            for model_id, model_priority in model_candidates:
                # Combine provider priority with model priority for base score
                combined_priority = min((provider.priority + model_priority) // 2, 100)
                all_candidates.append({
                    "provider_name": provider.name,
                    "provider": provider,
                    "provider_base_url": provider_base_url,
                    "key_record": key_record,
                    "secret_key": secret_key,
                    "model_id": model_id,
                    "base_priority": combined_priority,
                })

        # 3. Rank candidates by composite health score
        ranked = health_tracker.rank_candidates(all_candidates)

        if ranked:
            logger.info(
                "Adaptive routing for %s: top candidate %s/%s (score=%.1f), %d total candidates",
                agent_type,
                ranked[0]["provider_name"],
                ranked[0]["model_id"],
                ranked[0].get("composite_score", 0),
                len(ranked),
            )

        # 4. Try candidates in ranked order.
        # For interactive chat we cap at 2 to keep latency low.
        # For generation agents we try ALL available candidates before giving up.
        max_candidates = 2 if agent_type == "copilot_chat" else len(ranked)

        def _is_context_length_error(status_code: int, body: str) -> bool:
            """Return True when the API refused because the input was too long."""
            context_phrases = (
                "context length", "context window", "context_length_exceeded",
                "too many tokens", "input too large", "maximum context",
                "request too large", "prompt is too long", "tokens exceed",
                "reduce the length", "content too large", "payload too large",
            )
            body_lower = body.lower()
            if status_code in (400, 413, 422) and any(p in body_lower for p in context_phrases):
                return True
            # Some providers return 200 with an error payload
            if "context" in body_lower and "exceed" in body_lower:
                return True
            return False

        skipped_providers: set[str] = set()

        for candidate in ranked[:max_candidates]:
            provider = candidate["provider"]
            if provider.name in skipped_providers:
                continue

            provider_base_url = candidate["provider_base_url"]
            key_record = candidate["key_record"]
            secret_key = candidate["secret_key"]
            model_id = candidate["model_id"]

            # Skip if circuit breaker is open
            if not health_tracker.is_available(provider.name, model_id):
                logger.debug(
                    "Skipping circuit-broken %s/%s",
                    provider.name,
                    model_id,
                )
                continue

            start_time = time.time()
            logger.info(
                "Trying Provider %s model %s for agent %s (score=%.1f)",
                provider.name,
                model_id,
                agent_type,
                candidate.get("composite_score", 0),
            )

            try:
                url = f"{provider_base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://deckpilot.ai",
                    "X-Title": "deckpilotAI",
                }
                sys_prompt_final = system_prompt
                if response_schema and "json" not in sys_prompt_final.lower():
                    sys_prompt_final += "\n\nRespond with valid JSON matching the requested structure."

                is_reasoning_model = any(m in model_id.lower() for m in ("o1", "o3", "reasoner", "r1"))
                effective_model_id = (
                    model_id.replace("models/", "")
                    if provider.name == "gemini"
                    else model_id
                )
                payload: dict[str, Any] = {
                    "model": effective_model_id,
                    "messages": [
                        {"role": "system", "content": sys_prompt_final},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                if not is_reasoning_model:
                    payload["temperature"] = 0.2

                # Fast timeout for interactive chat / intelligence, standard timeout for heavy deck generation
                if agent_type == "copilot_chat":
                    timeout_val = 5.0
                    conn_timeout = 2.5
                elif agent_type in ("font_brand_detection", "title_intelligence"):
                    timeout_val = 6.0
                    conn_timeout = 3.0
                else:
                    timeout_val = float(settings.llm_read_timeout_seconds or 90.0)
                    conn_timeout = 8.0
                req_timeout = httpx.Timeout(timeout_val, connect=conn_timeout)
                async with httpx.AsyncClient(timeout=req_timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 400 and "temperature" in resp.text:
                        payload.pop("temperature", None)
                        resp = await client.post(url, headers=headers, json=payload)

                latency = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    resp_data = resp.json()
                    content = resp_data["choices"][0]["message"]["content"]
                    parsed = _parse_llm_response(content, response_schema)

                    # Record success in health tracker
                    health_tracker.record_success(provider.name, model_id, float(latency))

                    if provider.name == "openrouter":
                        OpenRouterModelManager.mark_model_success(model_id)
                    elif provider.name == "experientiallabs":
                        ExperientialLabsModelManager.mark_model_success(model_id)

                    key_record.last_used_at = now
                    key_record.failure_count = 0
                    db.commit()

                    if user_id:
                        try:
                            usage = UsageEvent(
                                user_id=user_id,
                                job_id=job_id,
                                provider_id=provider.id,
                                key_id=key_record.id,
                                model=model_id,
                                event_type="generation",
                                latency_ms=latency,
                                success=1,
                                created_at=now,
                                input_units=resp_data.get("usage", {}).get("prompt_tokens", 0),
                                output_units=resp_data.get("usage", {}).get("completion_tokens", 0),
                            )
                            db.add(usage)
                            db.commit()
                        except Exception:
                            db.rollback()
                            logger.warning("Failed to persist UsageEvent for %s", provider.name, exc_info=True)

                    logger.info("Provider %s model %s completed in %sms", provider.name, model_id, latency)
                    if latency > settings.slow_llm_threshold_ms:
                        DiagnosticsService.log_slow_operation(
                            component="llm",
                            operation=f"chat_completions ({agent_type})",
                            duration_ms=latency,
                            threshold_ms=settings.slow_llm_threshold_ms,
                            provider=provider.name,
                            additional_context={"model": model_id, "user_id": user_id, "job_id": job_id},
                        )
                    return parsed

                else:
                    raw_text = resp.text if isinstance(getattr(resp, "text", None), str) else ""

                    # ── Context-length retry strategy ─────────────────────────────────
                    # When the input is too large, retry the SAME provider up to 3 times
                    # with progressively compressed prompts before failing over.
                    if _is_context_length_error(resp.status_code, raw_text) and agent_type not in ("copilot_chat",):
                        from app.services.grounding_chunker import GroundingChunker
                        compressed_prompt = user_prompt
                        ctx_succeeded = False
                        for compression_level in (1, 2, 3):
                            compressed_prompt = GroundingChunker.compress_prompt_for_retry(
                                compressed_prompt, compression_level
                            )
                            logger.warning(
                                "Context-length error on %s/%s (HTTP %s) — retrying with compression level %d "
                                "(prompt %d -> %d chars)",
                                provider.name, model_id, resp.status_code,
                                compression_level, len(user_prompt), len(compressed_prompt),
                            )
                            try:
                                compressed_payload = dict(payload)
                                compressed_payload["messages"] = [
                                    {"role": "system", "content": sys_prompt_final},
                                    {"role": "user", "content": compressed_prompt},
                                ]
                                async with httpx.AsyncClient(timeout=req_timeout) as _ctx_client:
                                    ctx_resp = await _ctx_client.post(url, headers=headers, json=compressed_payload)
                                if ctx_resp.status_code == 200:
                                    ctx_data = ctx_resp.json()
                                    ctx_content = ctx_data["choices"][0]["message"]["content"]
                                    ctx_parsed = _parse_llm_response(ctx_content, response_schema)
                                    ctx_latency = int((time.time() - start_time) * 1000)
                                    health_tracker.record_success(provider.name, model_id, float(ctx_latency))
                                    logger.info(
                                        "Context-compression retry succeeded at level %d for %s/%s",
                                        compression_level, provider.name, model_id,
                                    )
                                    ctx_succeeded = True
                                    return ctx_parsed
                                elif not _is_context_length_error(ctx_resp.status_code, ctx_resp.text):
                                    # Different error — stop compressing, fall through to normal failure
                                    break
                                # Still a context error — try next compression level
                            except Exception as _ctx_err:
                                logger.warning(
                                    "Context-compression retry level %d failed for %s/%s: %s",
                                    compression_level, provider.name, model_id, _ctx_err,
                                )
                                break

                        if ctx_succeeded:
                            continue  # shouldn't reach here but guard anyway
                        # All 3 compression levels failed — fall through to normal failure handling
                    # ── End context-length retry ──────────────────────────────────────

                    # Record failure in health tracker
                    health_tracker.record_failure(provider.name, model_id)

                    if provider.name == "codecraft":
                        CodeCraftModelManager.mark_rate_limited(model_id, cooldown_seconds=60)
                    elif provider.name == "openrouter":
                        OpenRouterModelManager.mark_model_failure(model_id, status_code=resp.status_code)
                    elif provider.name == "experientiallabs":
                        is_unpayable = resp.status_code == 429 and ("model_requires_payment" in raw_text or "free credits" in raw_text)
                        cooldown = 3600 if is_unpayable else 60
                        ExperientialLabsModelManager.mark_model_failure(model_id, status_code=resp.status_code, cooldown_seconds=cooldown)

                    DiagnosticsService.log_external_api_failure(
                        provider=provider.name,
                        operation=f"chat_completions ({agent_type})",
                        error=f"HTTP {resp.status_code}: {raw_text[:300]}",
                        model_name=model_id,
                        provider_status_code=resp.status_code,
                        duration_ms=latency,
                        additional_context={"agent_type": agent_type, "user_id": user_id, "job_id": job_id},
                    )
                    is_provider_outage = (
                        provider.name != "gemini"
                        and (
                            resp.status_code in (502, 503, 504, 403)
                            or (resp.status_code == 429 and any(
                                phrase in raw_text.lower()
                                for phrase in ("card on file", "insufficient_quota", "requires_purchase", "free tier", "out of credits")
                            ))
                        )
                    )
                    if is_provider_outage:
                        logger.warning(
                            "Provider %s experienced provider-level failure (HTTP %s). Skipping remaining models for this provider.",
                            provider.name, resp.status_code,
                        )
                        skipped_providers.add(provider.name)

                    logger.warning("Provider %s model %s returned HTTP %s", provider.name, model_id, resp.status_code)
                    continue

            except Exception as model_err:
                # Record failure in health tracker
                health_tracker.record_failure(provider.name, model_id)

                if isinstance(model_err, (httpx.ConnectError, httpx.ConnectTimeout)):
                    logger.warning(
                        "Provider %s connection error (%s). Skipping remaining models for this provider.",
                        provider.name, model_err,
                    )
                    skipped_providers.add(provider.name)

                if provider.name == "codecraft":
                    CodeCraftModelManager.mark_rate_limited(model_id, cooldown_seconds=120)
                elif provider.name == "openrouter":
                    OpenRouterModelManager.mark_model_failure(model_id, status_code=500)
                elif provider.name == "experientiallabs":
                    ExperientialLabsModelManager.mark_model_failure(model_id, status_code=500, cooldown_seconds=300)

                DiagnosticsService.log_external_api_failure(
                    provider=provider.name,
                    operation=f"chat_completions ({agent_type})",
                    error=model_err,
                    model_name=model_id,
                    duration_ms=int((time.time() - start_time) * 1000),
                    additional_context={"agent_type": agent_type, "user_id": user_id, "job_id": job_id},
                )
                logger.warning("Provider %s model %s failed", provider.name, model_id, exc_info=True)
                continue

        # All providers and models exhausted — do NOT silently return hardcoded content.
        # Raise so the orchestrator can decide: retry with a simpler prompt, degrade gracefully,
        # or surface a meaningful error to the user.
        provider_names = ", ".join({c["provider_name"] for c in ranked}) or "none configured"
        raise RuntimeError(
            f"All LLM candidates exhausted for agent_type='{agent_type}'. "
            f"Tried providers: [{provider_names}]. "
            "Check provider keys, rate limits, and health tracker state."
        )
