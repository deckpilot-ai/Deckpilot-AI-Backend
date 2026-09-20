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

    # Fix common LLM JSON mistakes: trailing commas, control chars, JS comments
    sanitized = cleaned
    if obj_match:
        sanitized = obj_match.group(1).strip()
    # Remove trailing commas before } or ]
    sanitized = re.sub(r",\s*([}\]])", r"\1", sanitized)
    # Remove single-line // comments
    sanitized = re.sub(r"//[^\n]*", "", sanitized)
    # Remove control characters (except newline/tab)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", sanitized)
    try:
        res = json.loads(sanitized)
        return res if isinstance(res, dict) else {"data": res}
    except Exception:
        pass

    # If all JSON parsing attempts fail, return text wrapped in dict
    return {"text": cleaned}


def _validate_agent_output(
    agent_type: str,
    parsed: Any,
    response_schema: Any | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Validate that the parsed output fulfills the agent's semantic contract.

    Returns (is_valid, failure_reason, normalized_dict).
    Rejects malformed, empty, or unparseable text payloads so the router can
    failover to alternate models instead of propagating degraded data.
    """
    if not response_schema:
        if isinstance(parsed, dict) and "text" in parsed and len(str(parsed["text"]).strip()) > 0:
            return True, "", parsed
        if isinstance(parsed, str) and parsed.strip():
            return True, "", {"text": parsed.strip()}
        return True, "", parsed if isinstance(parsed, dict) else {"text": str(parsed)}

    # When response_schema is expected, raw text wrapper {"text": ...} indicates JSON parsing failed
    if isinstance(parsed, dict) and list(parsed.keys()) == ["text"]:
        raw_t = parsed["text"]
        match = re.search(r'(\{[\s\S]*\})', raw_t)
        if match:
            try:
                recovered = json.loads(match.group(1))
                if isinstance(recovered, dict) and len(recovered) > 0:
                    parsed = recovered
            except Exception:
                pass
        if isinstance(parsed, dict) and list(parsed.keys()) == ["text"]:
            return False, "Failed to parse structured JSON from LLM response", {}

    if not isinstance(parsed, (dict, list)):
        return False, f"Expected structured dict or list, got {type(parsed).__name__}", {}

    # Normalize list wrapping
    if isinstance(parsed, list):
        parsed = {"slides": parsed} if agent_type in ("deck_planner", "slide_writer") else {"data": parsed}

    # Unwrap common outer envelope keys: data, result, output, response, presentation, deck_spec, deck
    for env_key in ("data", "result", "output", "response", "presentation", "deck_spec", "deck"):
        if isinstance(parsed.get(env_key), dict) and ("slides" in parsed[env_key] or "brandStyle" in parsed[env_key]):
            parsed = parsed[env_key]
            break
        elif isinstance(parsed.get(env_key), list) and agent_type in ("deck_planner", "slide_writer"):
            parsed = {"slides": parsed[env_key]}
            break

    # Agent-specific contract verification
    if agent_type == "deck_planner":
        if "plan" in parsed and "slides" not in parsed:
            return True, "", parsed
        slides = parsed.get("slides")
        if not isinstance(slides, list) or len(slides) == 0:
            return False, "deck_planner output missing 'slides' array or array is empty", {}
        valid_slides = 0
        for s in slides:
            if isinstance(s, dict) and any(s.get(k) for k in ("headline", "message", "purpose", "title")):
                valid_slides += 1
        if valid_slides < max(1, len(slides) // 2):
            return False, f"deck_planner slides lack valid headlines ({valid_slides}/{len(slides)})", {}

    elif agent_type == "slide_writer":
        slides = parsed.get("slides") or parsed.get("data")
        if isinstance(slides, dict):
            slides = [slides]
        if not isinstance(slides, list) or len(slides) == 0:
            if any(parsed.get(k) for k in ("bullets", "headline", "message")):
                slides = [parsed]
                parsed = {"slides": slides}
            else:
                return False, "slide_writer output missing 'slides' list or slide items", {}
        has_content = any(isinstance(s, dict) and (s.get("bullets") or s.get("headline") or s.get("message")) for s in slides)
        if not has_content:
            return False, "slide_writer returned slides with zero bullets or headlines", {}

    elif agent_type == "font_brand_detection":
        if not any(parsed.get(k) for k in ("colors", "brandStyle", "palette", "typography", "subject", "theme")):
            return False, "font_brand_detection output missing style, colors, or typography keys", {}

    return True, "", parsed


class ProviderRouter:
    @staticmethod
    def sync_environment_providers(db: Session) -> None:
        """Auto-synchronize system AI providers and API keys from settings / environment into database."""
        provider_configs = [
            ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", settings.gemini_api_key, 35),
            ("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, 32),
            ("inceptionlabs", settings.inceptionlabs_base_url or "https://api.inceptionlabs.ai/v1", settings.inceptionlabs_api_key, 30),
            ("apmix", settings.apmix_base_url or "https://api.apmix.ai/v1", settings.apmix_api_key, 28),
            ("bynara", settings.bynara_base_url or "https://router.bynara.id/v1", settings.bynara_api_key, 27),
            ("nvidia", settings.nvidia_base_url or "https://integrate.api.nvidia.com/v1", settings.nvidia_api_key, 25),
            ("bazaarlink", settings.bazaarlink_base_url or "https://api.bazaarlink.ai/v1", settings.bazaarlink_api_key, 20),
            ("routeway", settings.routeway_base_url or "https://api.routeway.ai/v1", settings.routeway_api_key, 18),
            ("codecraft", settings.codecraft_base_url or "https://codecraftapi.com/v1", settings.codecraft_api_key, 15),
            ("experientiallabs", settings.experientiallabs_base_url or "https://api.experientiallabs.ai/v1", settings.effective_experientiallabs_api_key, 12),
            ("openrouter", "https://openrouter.ai/api/v1", settings.openrouter_api_key, 10),
            ("openai", "https://api.openai.com/v1", settings.openai_api_key, 8),
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

                # Curated default models for each provider (always upsert to keep current)
                default_models = []
                if name == "gemini":
                    default_models = [
                        {"model_id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "priority": 100, "enabled": 1, "context_length": 1000000},
                        {"model_id": "gemini-flash-latest", "display_name": "Gemini Flash Latest", "priority": 98, "enabled": 1, "context_length": 1000000},
                        {"model_id": "gemini-2.5-flash-lite", "display_name": "Gemini 2.5 Flash Lite", "priority": 95, "enabled": 1, "context_length": 1000000},
                        {"model_id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "priority": 90, "enabled": 1, "context_length": 1000000},
                        {"model_id": "gemini-3.8-flash", "display_name": "Gemini 3.8 Flash (Deprecated)", "priority": 1, "enabled": 0, "context_length": 1000000},
                        {"model_id": "gemini-3.7-flash", "display_name": "Gemini 3.7 Flash (Deprecated)", "priority": 1, "enabled": 0, "context_length": 1000000},
                        {"model_id": "gemini-3.5-flash", "display_name": "Gemini 3.5 Flash (Deprecated)", "priority": 1, "enabled": 0, "context_length": 1000000},
                    ]
                elif name == "groq":
                    default_models = [
                        {"model_id": "openai/gpt-oss-120b", "display_name": "GPT-OSS 120B (Ultra-Fast)", "priority": 100, "enabled": 1, "context_length": 131072},
                        {"model_id": "qwen/qwen3.8-27b", "display_name": "Qwen 3.8 27B", "priority": 95, "enabled": 1, "context_length": 131072},
                        {"model_id": "openai/gpt-oss-20b", "display_name": "GPT-OSS 20B", "priority": 90, "enabled": 1, "context_length": 131072},
                        {"model_id": "groq/compound-mini", "display_name": "Compound Mini", "priority": 85, "enabled": 1, "context_length": 131072},
                        {"model_id": "llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B (Deprecated)", "priority": 1, "enabled": 0, "context_length": 128000},
                        {"model_id": "allam-2-7b", "display_name": "Allam 2 7B (Deprecated)", "priority": 1, "enabled": 0, "context_length": 4096},
                    ]
                elif name == "inceptionlabs":
                    default_models = [
                        {"model_id": "mercury-2.5", "display_name": "Mercury 2.5 (Diffusion LLM • 316 TPS)", "priority": 100, "enabled": 1, "context_length": 260000},
                        {"model_id": "mercury-2", "display_name": "Mercury 2 (Discrete Diffusion • 255 TPS)", "priority": 95, "enabled": 1, "context_length": 128000},
                    ]
                elif name == "nvidia":
                    default_models = [
                        {"model_id": "deepseek-ai/deepseek-v4-flash-0731", "display_name": "DeepSeek V4 Flash 0731", "priority": 98, "enabled": 1, "context_length": 128000},
                        {"model_id": "google/gemma-3-12b-it", "display_name": "Gemma 3 12B IT", "priority": 95, "enabled": 1, "context_length": 128000},
                        {"model_id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "display_name": "Nemotron 3 Nano Omni 30B", "priority": 90, "enabled": 1, "context_length": 128000},
                        {"model_id": "meta/llama-3.2-11b-vision-instruct", "display_name": "Llama 3.2 11B Vision Instruct", "priority": 85, "enabled": 1, "context_length": 128000},
                    ]
                elif name == "bazaarlink":
                    default_models = [
                        {"model_id": "auto:free", "display_name": "Auto Router (Free)", "priority": 100, "enabled": 1, "context_length": 128000},
                        {"model_id": "qwen/qwen3.7-flash:free", "display_name": "Qwen 3.7 Flash (Free)", "priority": 98, "enabled": 1, "context_length": 128000},
                        {"model_id": "auto", "display_name": "Auto Router", "priority": 96, "enabled": 1, "context_length": 128000},
                        {"model_id": "deepseek-v4-flash", "display_name": "DeepSeek V4 Flash", "priority": 94, "enabled": 1, "context_length": 128000},
                        {"model_id": "qwen3.8-max", "display_name": "Qwen 3.8 Max", "priority": 92, "enabled": 1, "context_length": 1000000},
                        {"model_id": "claude-sonnet-4.6", "display_name": "Claude Sonnet 4.6", "priority": 90, "enabled": 1, "context_length": 200000},
                        {"model_id": "glm-5", "display_name": "GLM 5", "priority": 88, "enabled": 1, "context_length": 128000},
                    ]
                elif name == "routeway":
                    default_models = [
                        {"model_id": "deepseek-v4-flash:free", "display_name": "DeepSeek V4 Flash (Free)", "priority": 100, "enabled": 1, "context_length": 128000},
                        {"model_id": "minimax-m2.7:free", "display_name": "MiniMax M2.7 (Free)", "priority": 98, "enabled": 1, "context_length": 128000},
                        {"model_id": "muse-glimmer-30b:free", "display_name": "Meta Glimmer 30B (Free)", "priority": 96, "enabled": 1, "context_length": 128000},
                        {"model_id": "kimi-k2.6:free", "display_name": "Moonshot Kimi K2.6 (Free)", "priority": 94, "enabled": 1, "context_length": 128000},
                        {"model_id": "deepseek-v4-flash", "display_name": "DeepSeek V4 Flash", "priority": 92, "enabled": 1, "context_length": 128000},
                        {"model_id": "qwen3.8-max", "display_name": "Qwen 3.8 Max", "priority": 90, "enabled": 1, "context_length": 1000000},
                        {"model_id": "claude-fable-5-1", "display_name": "Claude Fable 5.1", "priority": 88, "enabled": 1, "context_length": 200000},
                    ]
                elif name == "apmix":
                    default_models = [
                        {"model_id": "gemini-2.5-flash-free", "display_name": "Gemini 2.5 Flash Free (Rank #1)", "priority": 100, "enabled": 1, "context_length": 1000000},
                        {"model_id": "gpt-5.6-luna-free", "display_name": "GPT-5.6 Luna Free (Rank #2)", "priority": 95, "enabled": 1, "context_length": 128000},
                        {"model_id": "kimi-k3-free", "display_name": "Kimi K3 Free (Rank #3)", "priority": 90, "enabled": 1, "context_length": 128000},
                        {"model_id": "grok-4.6-free", "display_name": "Grok 4.6 Free (Rank #4)", "priority": 85, "enabled": 1, "context_length": 128000},
                        {"model_id": "deepseek-v4.1-flash-free", "display_name": "DeepSeek V4.1 Flash Free (Rank #5)", "priority": 80, "enabled": 1, "context_length": 1048576},
                        {"model_id": "muse-spark-1.3-free", "display_name": "Muse Spark 1.3 Free (Rank #6)", "priority": 70, "enabled": 1, "context_length": 128000},
                    ]
                elif name == "bynara":
                    default_models = [
                        {"model_id": "ling-3.0-flash-vl-free", "display_name": "Ling 3.0 Flash VL (Free • Vision)", "priority": 100, "enabled": 1, "context_length": 262144},
                        {"model_id": "ling-3.0-flash-fin-free", "display_name": "Ling 3.0 Flash Fin (Free • Text)", "priority": 98, "enabled": 1, "context_length": 262144},
                        {"model_id": "nemotron-3.5-lightning-free", "display_name": "Nemotron 3.5 Lightning (Free • 1M)", "priority": 95, "enabled": 1, "context_length": 1048576},
                        {"model_id": "nemotron-3-ultra-free", "display_name": "Nemotron 3 Ultra (Free • 1M)", "priority": 92, "enabled": 1, "context_length": 1048576},
                        {"model_id": "ling-3.0-flash-sante-free", "display_name": "Ling 3.0 Flash Sante (Free • Text)", "priority": 90, "enabled": 1, "context_length": 262144},
                        {"model_id": "nemotron-3-super-free", "display_name": "Nemotron 3 Super (Free • Text)", "priority": 88, "enabled": 1, "context_length": 262144},
                        {"model_id": "nex-n2.5-pro", "display_name": "Nex N2.5 Pro (Free • Vision)", "priority": 85, "enabled": 1, "context_length": 262144},
                        {"model_id": "laguna-s-2.1", "display_name": "Laguna S-2.1 (Free • Text)", "priority": 80, "enabled": 1, "context_length": 262144},
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
                            if "bynara" in cleaned_url:
                                free_model_ids = {
                                    "ling-3.0-flash-vl-free",
                                    "ling-3.0-flash-fin-free",
                                    "nemotron-3.5-lightning-free",
                                    "nemotron-3-ultra-free",
                                    "ling-3.0-flash-sante-free",
                                    "nemotron-3-super-free",
                                    "nex-n2.5-pro",
                                    "laguna-s-2.1",
                                }
                                discovered = [m for m in discovered if m["id"] in free_model_ids]
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
        elif "bynara" in cleaned_url:
            bynara_curated = [
                ("ling-3.0-flash-vl-free", "Ling 3.0 Flash VL (Free • Vision)", 262144, "Multimodal vision & text model (Free)", 100),
                ("ling-3.0-flash-fin-free", "Ling 3.0 Flash Fin (Free • Text)", 262144, "Financial & analytical generation model (Free)", 98),
                ("nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning (Free • 1M)", 1048576, "1M context ultra-fast instruction model (Free)", 95),
                ("nemotron-3-ultra-free", "Nemotron 3 Ultra (Free • 1M)", 1048576, "1M context flagship reasoning model (Free)", 92),
                ("ling-3.0-flash-sante-free", "Ling 3.0 Flash Sante (Free • Text)", 262144, "Domain scientific & knowledge model (Free)", 90),
                ("nemotron-3-super-free", "Nemotron 3 Super (Free • Text)", 262144, "High throughput reasoning model (Free)", 88),
                ("nex-n2.5-pro", "Nex N2.5 Pro (Free • Vision)", 262144, "Vision & multimodal presentation layout model (Free)", 85),
                ("laguna-s-2.1", "Laguna S-2.1 (Free • Text)", 262144, "Low-latency text generation model (100% off)", 80),
            ]
            return [
                {
                    "id": mid,
                    "name": mname,
                    "context_length": ctx,
                    "description": desc,
                    "default_priority": prio,
                }
                for mid, mname, ctx, desc, prio in bynara_curated
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
        elif "nvidia" in cleaned_url:
            nvidia_curated = [
                ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "Nemotron 3 Nano Omni 30B (Reasoning)", 128000, "Ultra-fast reasoning model with precise JSON output", 100),
                ("poolside/laguna-xs-2.1", "Laguna XS 2.1 (Ultra-Fast)", 128000, "Sub-500ms low-latency model", 98),
                ("nvidia/nemotron-3-super-120b-a12b", "Nemotron 3 Super 120B (Flagship)", 128000, "NVIDIA 120B Flagship model for high-depth tasks", 96),
                ("nvidia/nemotron-3.5-lightning-30b-a3b", "Nemotron 3.5 Lightning 30B", 128000, "NVIDIA Nemotron 3.5 Lightning architecture", 94),
                ("openai/gpt-oss-20b", "GPT OSS 20B", 128000, "OpenAI architecture running on NVIDIA NIM", 92),
                ("nvidia/ising-calibration-1.5-31b", "Ising Calibration 1.5 31B", 128000, "31B parameter high precision model", 90),
                ("meta/llama-3.2-11b-vision-instruct", "Llama 3.2 11B Vision Instruct", 128000, "Multimodal vision & text instruction tuned", 88),
            ]
            return [
                {
                    "id": mid,
                    "name": mname,
                    "context_length": ctx,
                    "description": desc,
                    "default_priority": prio,
                }
                for mid, mname, ctx, desc, prio in nvidia_curated
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
    async def _execute_model_ping(
        provider_id: str,
        provider_name: str,
        base_url: str,
        secret_key: str,
        model_id: str,
        model_db_id: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        cleaned_url = base_url.rstrip("/")
        if cleaned_url.endswith("/chat/completions"):
            url = cleaned_url
        else:
            url = f"{cleaned_url}/chat/completions"

        effective_model_id = (
            model_id.replace("models/", "")
            if provider_name == "gemini"
            else model_id
        )

        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "HTTP-Referer": "https://deckpilot.ai",
            "X-Title": "deckpilotAI Diagnostic Test",
        }

        payload = {
            "model": effective_model_id,
            "messages": [{"role": "user", "content": "Respond with 'OK'"}],
            "max_tokens": 20,
            "temperature": 0.1,
        }

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
                resp = await client.post(url, json=payload, headers=headers)
                elapsed_ms = round((time.time() - t0) * 1000, 1)

                # If URL didn't have /v1 and returned HTML or 404, try /v1/chat/completions fallback
                content_type = resp.headers.get("content-type", "")
                if ("text/html" in content_type or resp.status_code in (404, 405)) and "/v1" not in cleaned_url:
                    alt_url = f"{cleaned_url}/v1/chat/completions"
                    try:
                        alt_resp = await client.post(alt_url, json=payload, headers=headers)
                        alt_content_type = alt_resp.headers.get("content-type", "")
                        if "application/json" in alt_content_type or alt_resp.status_code == 200:
                            resp = alt_resp
                            content_type = alt_content_type
                            elapsed_ms = round((time.time() - t0) * 1000, 1)
                    except Exception:
                        pass

                # Check for HTML content
                if "text/html" in content_type:
                    health_tracker.record_failure(provider_name, model_id)
                    return {
                        "success": False,
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "model_id": model_id,
                        "model_db_id": model_db_id,
                        "display_name": display_name or model_id,
                        "latency_ms": elapsed_ms,
                        "status_code": resp.status_code,
                        "error": f"Endpoint returned HTML instead of JSON. Base URL might need /v1 suffix (e.g. {cleaned_url}/v1).",
                    }

                # Safe JSON parse
                data = None
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if resp.status_code == 200 and isinstance(data, dict):
                    content = ""
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        raw_content = choice.get("message", {}).get("content") if isinstance(choice.get("message"), dict) else choice.get("text")
                        if raw_content is None:
                            raw_content = ""
                        content = str(raw_content).strip()
                    
                    health_tracker.record_success(provider_name, model_id, elapsed_ms)
                    return {
                        "success": True,
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "model_id": model_id,
                        "model_db_id": model_db_id,
                        "display_name": display_name or model_id,
                        "latency_ms": elapsed_ms,
                        "status_code": 200,
                        "response_text": content[:150],
                        "usage": data.get("usage"),
                    }
                else:
                    health_tracker.record_failure(provider_name, model_id)
                    err_msg = ""
                    if isinstance(data, dict) and "error" in data:
                        err_obj = data["error"]
                        if isinstance(err_obj, dict):
                            err_msg = err_obj.get("message") or str(err_obj)
                        else:
                            err_msg = str(err_obj)
                    if not err_msg:
                        err_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
                    return {
                        "success": False,
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "model_id": model_id,
                        "model_db_id": model_db_id,
                        "display_name": display_name or model_id,
                        "latency_ms": elapsed_ms,
                        "status_code": resp.status_code,
                        "error": err_msg,
                    }
        except Exception as exc:
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            health_tracker.record_failure(provider_name, model_id)
            return {
                "success": False,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model_id": model_id,
                "model_db_id": model_db_id,
                "display_name": display_name or model_id,
                "latency_ms": elapsed_ms,
                "error": str(exc),
            }

    @staticmethod
    async def test_provider_model(
        db: Session,
        provider_id: str,
        model_id: str,
        model_db_id: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Send a diagnostic ping prompt to test a specific model on a provider and measure latency/correctness."""
        provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
        if not provider:
            raise ValueError("Provider not found")
        
        provider_base_url = validate_provider_base_url(provider.base_url)
        active_key_tuple = ProviderRouter.select_active_key(db, provider.id)
        if not active_key_tuple:
            return {
                "success": False,
                "provider_id": provider_id,
                "provider_name": provider.name,
                "model_id": model_id,
                "model_db_id": model_db_id,
                "display_name": display_name or model_id,
                "error": f"No active/valid API key found for provider '{provider.name}'",
            }
        
        _, secret_key = active_key_tuple
        return await ProviderRouter._execute_model_ping(
            provider_id=provider.id,
            provider_name=provider.name,
            base_url=provider_base_url,
            secret_key=secret_key,
            model_id=model_id,
            model_db_id=model_db_id,
            display_name=display_name,
        )

    @staticmethod
    async def test_provider_all_models(
        db: Session,
        provider_id: str,
    ) -> list[dict[str, Any]]:
        """Test all configured models for a provider concurrently."""
        import asyncio
        provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
        if not provider:
            raise ValueError("Provider not found")
        
        provider_base_url = validate_provider_base_url(provider.base_url)
        active_key_tuple = ProviderRouter.select_active_key(db, provider.id)
        if not active_key_tuple:
            raise ValueError(f"No active/valid API key configured for provider '{provider.name}'")
        
        _, secret_key = active_key_tuple

        models = db.scalars(
            select(AIProviderModel)
            .where(AIProviderModel.provider_id == provider_id)
            .order_by(AIProviderModel.priority.desc())
        ).all()

        model_items: list[tuple[str, str | None, str | None]] = []
        if not models:
            fetched = await ProviderRouter.fetch_provider_models(provider_base_url, api_key=secret_key)
            model_items = [(m["id"], None, m.get("name")) for m in fetched[:6]]
        else:
            model_items = [(m.model_id, m.id, m.display_name) for m in models]

        tasks = [
            ProviderRouter._execute_model_ping(
                provider_id=provider.id,
                provider_name=provider.name,
                base_url=provider_base_url,
                secret_key=secret_key,
                model_id=mid,
                model_db_id=mdbid,
                display_name=dname,
            )
            for mid, mdbid, dname in model_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

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
                    model_candidates = [
                        ("openai/gpt-oss-120b", 100),
                        ("qwen/qwen3.8-27b", 95),
                        ("openai/gpt-oss-20b", 90),
                    ]
                elif "gemini" in p_name:
                    model_candidates = [
                        ("gemini-2.5-flash", 100),
                        ("gemini-flash-latest", 98),
                        ("gemini-2.5-flash-lite", 95),
                        ("gemini-2.5-pro", 90),
                    ]
                elif "nvidia" in p_name:
                    model_candidates = [
                        ("deepseek-ai/deepseek-v4-flash-0731", 98),
                        ("google/gemma-3-12b-it", 95),
                        ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", 90),
                        ("meta/llama-3.2-11b-vision-instruct", 85),
                    ]
                elif "routeway" in p_name:
                    model_candidates = [
                        ("deepseek-v4-flash:free", 100),
                        ("minimax-m2.7:free", 98),
                        ("muse-glimmer-30b:free", 96),
                        ("kimi-k2.6:free", 94),
                        ("deepseek-v4-flash", 92),
                        ("qwen3.8-max", 90),
                        ("claude-fable-5-1", 88),
                    ]
                elif "bazaarlink" in p_name:
                    model_candidates = [
                        ("auto:free", 100),
                        ("qwen/qwen3.7-flash:free", 98),
                        ("auto", 96),
                        ("deepseek-v4-flash", 94),
                        ("qwen3.8-max", 92),
                        ("claude-sonnet-4.6", 90),
                        ("glm-5", 88),
                    ]
                elif "inceptionlabs" in p_name:
                    model_candidates = [
                        ("mercury-2.5", 100),
                        ("mercury-2", 95),
                    ]
                elif "apmix" in p_name:
                    model_candidates = [
                        ("gemini-2.5-flash-free", 100),
                        ("gpt-5.6-luna-free", 95),
                        ("kimi-k3-free", 90),
                        ("grok-4.6-free", 85),
                        ("deepseek-v4.1-flash-free", 80),
                        ("muse-spark-1.3-free", 70),
                    ]
                elif "bynara" in p_name:
                    model_candidates = [
                        ("ling-3.0-flash-vl-free", 100),
                        ("ling-3.0-flash-fin-free", 98),
                        ("nemotron-3.5-lightning-free", 95),
                        ("nemotron-3-ultra-free", 92),
                        ("ling-3.0-flash-sante-free", 90),
                        ("nemotron-3-super-free", 88),
                        ("nex-n2.5-pro", 85),
                        ("laguna-s-2.1", 80),
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

                if agent_type == "copilot_chat":
                    timeout_val = 10.0
                    conn_timeout = 3.5
                elif agent_type in ("font_brand_detection", "title_intelligence"):
                    timeout_val = 15.0
                    conn_timeout = 4.0
                elif agent_type == "slide_writer":
                    # Slide writer handles batches of 5 slides with grounding context;
                    # needs enough time for large reference document decks (25 slides).
                    timeout_val = 50.0
                    conn_timeout = 5.0
                elif agent_type == "deck_planner":
                    # Deck planner must generate 20-25 slide outlines from reference docs;
                    # orchestrator outer timeout is 90s so we give 65s per provider attempt.
                    timeout_val = 65.0
                    conn_timeout = 5.0
                else:
                    timeout_val = float(min(settings.llm_read_timeout_seconds or 35.0, 35.0))
                    conn_timeout = 4.0
                req_timeout = httpx.Timeout(timeout_val, connect=conn_timeout)
                async with httpx.AsyncClient(timeout=req_timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 400 and "temperature" in resp.text:
                        payload.pop("temperature", None)
                        resp = await client.post(url, headers=headers, json=payload)

                latency = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    try:
                        resp_data = resp.json()
                    except Exception as json_err:
                        logger.warning(
                            "Provider %s model %s returned 200 OK but invalid JSON payload: %s",
                            provider.name, model_id, json_err,
                        )
                        health_tracker.record_failure(provider.name, model_id)
                        continue
                    # Robust content extraction — handle missing/null content from providers
                    choices = resp_data.get("choices") or []
                    if not choices:
                        logger.warning(
                            "Provider %s model %s returned 200 but no choices — treating as failure",
                            provider.name, model_id,
                        )
                        health_tracker.record_failure(provider.name, model_id)
                        continue
                    message = choices[0].get("message") or {}
                    content = message.get("content")
                    if content is None:
                        # Some providers put content in delta or text fields
                        content = (
                            choices[0].get("text")
                            or (choices[0].get("delta") or {}).get("content")
                            or ""
                        )
                    if not content or not content.strip():
                        logger.warning(
                            "Provider %s model %s returned 200 but empty/null content — treating as failure",
                            provider.name, model_id,
                        )
                        health_tracker.record_failure(provider.name, model_id)
                        continue
                    parsed = _parse_llm_response(content, response_schema)
                    is_valid, fail_reason, normalized = _validate_agent_output(agent_type, parsed, response_schema)
                    if not is_valid:
                        logger.warning(
                            "Provider %s model %s output failed contract validation for %s: %s — failing over to next model/provider",
                            provider.name, model_id, agent_type, fail_reason,
                        )
                        health_tracker.record_failure(provider.name, model_id)
                        continue
                    parsed = normalized

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
                    raw_lower = raw_text.lower()
                    # Only skip the entire provider account if it is truly unauthenticated or out of credits.
                    # Individual model rate limits (429 TPM/RPM) or temporary 502/503/504 overloads should
                    # failover to other configured models under the same provider before moving to the next provider.
                    is_account_outage = (
                        resp.status_code in (401, 402)
                        or any(phrase in raw_lower for phrase in (
                            "insufficient funds", "insufficient credits", "out of credits", "no credits remaining",
                            "requires_purchase", "card on file", "account suspended", "invalid_api_key",
                        ))
                    )
                    if is_account_outage:
                        logger.warning(
                            "Provider %s experienced account-level failure (HTTP %s: %s). Skipping remaining models for this provider.",
                            provider.name, resp.status_code, raw_text[:120],
                        )
                        skipped_providers.add(provider.name)

                    logger.warning("Provider %s model %s returned HTTP %s (failing over to next candidate)", provider.name, model_id, resp.status_code)
                    continue

            except Exception as model_err:
                # Record failure in health tracker
                health_tracker.record_failure(provider.name, model_id)

                # Only skip the entire provider if the network host cannot be reached at all (ConnectError / DNS failure)
                if isinstance(model_err, httpx.ConnectError):
                    logger.warning(
                        "Provider %s host connection error (%s). Skipping provider.",
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

    @staticmethod
    async def stream_llm(
        db: Session,
        agent_type: str,
        system_prompt: str,
        messages: list[dict[str, str]] | None = None,
        user_prompt: str | None = None,
        user_id: str | None = None,
        job_id: str | None = None,
    ):
        """
        Asynchronously streams token deltas using adaptive health-aware routing.
        Supports full chronological conversation history and automatic provider failover.
        """
        now = int(time.time())

        # 1. Get enabled providers
        providers = db.scalars(
            select(AIProvider)
            .where(AIProvider.enabled == 1)
            .order_by(desc(AIProvider.priority))
        ).all()

        all_candidates: list[dict[str, Any]] = []
        for provider in providers:
            try:
                provider_base_url = validate_provider_base_url(provider.base_url)
            except ValueError:
                continue

            active_key_tuple = ProviderRouter.select_active_key(db, provider.id)
            if not active_key_tuple:
                continue
            key_record, secret_key = active_key_tuple

            configured_models = db.scalars(
                select(AIProviderModel)
                .where(AIProviderModel.provider_id == provider.id, AIProviderModel.enabled == 1)
                .order_by(desc(AIProviderModel.priority))
            ).all()

            model_candidates: list[tuple[str, int]] = []
            if configured_models:
                model_candidates = [(m.model_id, m.priority) for m in configured_models]
            else:
                p_name = provider.name.lower()
                if "gemini" in p_name:
                    model_candidates = [("gemini-2.5-flash", 100), ("gemini-flash-latest", 98)]
                elif "groq" in p_name:
                    model_candidates = [("openai/gpt-oss-120b", 100), ("qwen/qwen3.8-27b", 95)]
                elif "inceptionlabs" in p_name:
                    model_candidates = [("mercury-2.5", 100), ("mercury-2", 95)]
                elif "apmix" in p_name:
                    model_candidates = [("gemini-2.5-flash-free", 100), ("gpt-5.6-luna-free", 95)]
                elif "bynara" in p_name:
                    model_candidates = [("ling-3.0-flash-vl-free", 100), ("ling-3.0-flash-fin-free", 98)]
                elif "vyce" in p_name:
                    model_candidates = [("claude-sonnet-4-6", 100), ("deepseek-v4-flash", 95)]
                elif "openai" in p_name:
                    model_candidates = [("gpt-4o-mini", 90), ("gpt-4o", 95)]
                else:
                    model_candidates = [("default", 50)]

            for model_id, model_priority in model_candidates:
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

        ranked = health_tracker.rank_candidates(all_candidates)
        if not ranked:
            raise RuntimeError("No available LLM providers configured for streaming.")

        # Construct payload messages
        convo_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if messages and len(messages) > 0:
            for m in messages:
                if m.get("role") and m.get("content"):
                    convo_messages.append({"role": m["role"], "content": m["content"]})
        elif user_prompt:
            convo_messages.append({"role": "user", "content": user_prompt})

        has_yielded = False
        last_error = None

        for candidate in ranked[:5]:
            provider = candidate["provider"]
            provider_base_url = candidate["provider_base_url"]
            key_record = candidate["key_record"]
            secret_key = candidate["secret_key"]
            model_id = candidate["model_id"]

            if not health_tracker.is_available(provider.name, model_id):
                continue

            start_time = time.time()
            effective_model_id = (
                model_id.replace("models/", "")
                if provider.name == "gemini"
                else model_id
            )
            is_reasoning_model = any(m in model_id.lower() for m in ("o1", "o3", "reasoner", "r1"))

            url = f"{provider_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "HTTP-Referer": "https://deckpilot.ai",
                "X-Title": "deckpilotAI",
            }
            payload: dict[str, Any] = {
                "model": effective_model_id,
                "messages": convo_messages,
                "stream": True,
            }
            if not is_reasoning_model:
                payload["temperature"] = 0.3

            try:
                req_timeout = httpx.Timeout(30.0, connect=5.0)
                async with httpx.AsyncClient(timeout=req_timeout) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code != 200:
                            body_text = await resp.aread()
                            health_tracker.record_failure(provider.name, model_id)
                            logger.warning("Stream provider %s/%s failed with HTTP %s: %s", provider.name, model_id, resp.status_code, body_text[:200])
                            last_error = f"HTTP {resp.status_code}"
                            continue

                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    choices = chunk.get("choices") or []
                                    if choices:
                                        delta_content = ""
                                        c0 = choices[0]
                                        if isinstance(c0, dict):
                                            if "delta" in c0:
                                                d = c0["delta"]
                                                if isinstance(d, dict):
                                                    delta_content = d.get("content") or d.get("text") or ""
                                                elif isinstance(d, str):
                                                    delta_content = d
                                            elif "text" in c0:
                                                delta_content = c0["text"]
                                            elif "message" in c0 and isinstance(c0["message"], dict):
                                                delta_content = c0["message"].get("content") or ""

                                        if delta_content:
                                            has_yielded = True
                                            yield str(delta_content)
                                except Exception:
                                    continue

                        if has_yielded:
                            latency = int((time.time() - start_time) * 1000)
                            health_tracker.record_success(provider.name, model_id, float(latency))
                            key_record.last_used_at = now
                            key_record.failure_count = 0
                            db.commit()
                            return

            except Exception as stream_err:
                health_tracker.record_failure(provider.name, model_id)
                logger.warning("Streaming error on %s/%s: %s", provider.name, model_id, stream_err)
                last_error = str(stream_err)
                if has_yielded:
                    return
                continue

        if not has_yielded:
            # Fallback to standard robust call_llm
            try:
                user_msg_text = convo_messages[-1]["content"] if convo_messages else "Hello"
                fallback_res = await ProviderRouter.call_llm(
                    db=db,
                    agent_type=agent_type,
                    system_prompt=system_prompt,
                    user_prompt=user_msg_text,
                    user_id=user_id,
                )
                text = fallback_res.get("text") or fallback_res.get("content") or ""
                if text:
                    yield text
                    return
            except Exception as fb_err:
                logger.warning("Fallback call_llm failed: %s", fb_err)

            # Final static fallback
            fallback_text = (
                "<thinking>\n1. Process user request directly.\n</thinking>\n\n"
                "<answer>\nI am your **deckpilotAI Copilot**. All stream services are currently busy, but I am standing by to help you research topics, design presentations, or analyze documents.\n</answer>"
            )
            yield fallback_text

