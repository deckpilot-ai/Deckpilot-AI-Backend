"""AI Provider Router, Key Security, and OpenRouter Free Model Cascade Engine."""

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
from app.models.provider import AgentRoute, AIKey, AIProvider
from app.services.experientiallabs_models import ExperientialLabsModelManager
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
        """Auto-synchronize API keys from settings / environment into database."""
        provider_configs = [
            ("experientiallabs", settings.experientiallabs_base_url, settings.effective_experientiallabs_api_key, 11),
            ("openrouter", "https://openrouter.ai/api/v1", settings.openrouter_api_key, 10),
            ("openai", "https://api.openai.com/v1", settings.openai_api_key, 9),
            ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", settings.gemini_api_key, 8),
            ("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, 7),
            ("mistral", "https://api.mistral.ai/v1", settings.mistral_api_key, 6),
            ("anthropic", "https://api.anthropic.com/v1", settings.anthropic_api_key, 5),
        ]

        for name, base_url, key_secret, priority in provider_configs:
            if not key_secret or not key_secret.strip():
                continue

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

            # Check if this key already exists
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
        Executes an LLM call through the quality-sequenced cascade.
        Automatically tries highest quality free model first; if it fails, passes the exact context
        to the next free model in sequence.
        """
        now = int(time.time())

        # 1. Ensure providers from environment are synchronized
        ProviderRouter.sync_environment_providers(db)

        # 2. Check for ExperientialLabs provider
        explabs_provider = db.scalar(
            select(AIProvider).where(AIProvider.name == "experientiallabs", AIProvider.enabled == 1)
        )

        # 3. If ExperientialLabs is available, execute ExperientialLabs Free Model Cascade
        if explabs_provider:
            try:
                explabs_base_url = validate_provider_base_url(explabs_provider.base_url)
            except ValueError:
                logger.error("Disabled unsafe ExperientialLabs provider URL for provider %s", explabs_provider.id)
                explabs_provider.enabled = 0
                db.commit()
                explabs_provider = None

        if explabs_provider:
            active_key_tuple = ProviderRouter.select_active_key(db, explabs_provider.id)
            if active_key_tuple:
                key_record, secret_key = active_key_tuple
                ranked_free_models = await ExperientialLabsModelManager.get_ranked_candidates(
                    api_key=secret_key,
                    base_url=explabs_base_url,
                )

                for candidate in ranked_free_models[:5]:
                    model_id = candidate["id"]
                    start_time = time.time()
                    logger.info(
                        "Trying ExperientialLabs model %s for agent %s (quality_score=%s)",
                        model_id,
                        agent_type,
                        candidate.get("quality_score"),
                    )

                    try:
                        url = f"{explabs_base_url}/chat/completions"
                        headers = {
                            "Authorization": f"Bearer {secret_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://deckpilot.ai",
                            "X-Title": "deckpilotAI",
                        }
                        sys_prompt_final = system_prompt
                        if response_schema and "json" not in sys_prompt_final.lower():
                            sys_prompt_final += "\n\nRespond with valid JSON matching the requested structure."

                        payload: dict[str, Any] = {
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": sys_prompt_final},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.2,
                        }
                        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_read_timeout_seconds, connect=10.0)) as client:
                            resp = await client.post(url, headers=headers, json=payload)

                        latency = int((time.time() - start_time) * 1000)

                        if resp.status_code == 200:
                            resp_data = resp.json()
                            content = resp_data["choices"][0]["message"]["content"]
                            parsed = _parse_llm_response(content, response_schema)

                            ExperientialLabsModelManager.mark_model_success(model_id)
                            key_record.last_used_at = now
                            key_record.failure_count = 0
                            db.commit()

                            if user_id:
                                usage = UsageEvent(
                                    user_id=user_id,
                                    job_id=job_id,
                                    provider_id=explabs_provider.id,
                                    key_id=key_record.id,
                                    model=model_id,
                                    event_type="generation",
                                    latency_ms=latency,
                                    success=1,
                                    created_at=now,
                                    prompt_tokens=resp_data.get("usage", {}).get("prompt_tokens", 0),
                                    completion_tokens=resp_data.get("usage", {}).get("completion_tokens", 0),
                                )
                                db.add(usage)
                                db.commit()

                            logger.info("ExperientialLabs model %s completed in %sms", model_id, latency)
                            return parsed

                        else:
                            ExperientialLabsModelManager.mark_model_failure(model_id, status_code=resp.status_code)
                            logger.warning("ExperientialLabs model %s returned HTTP %s", model_id, resp.status_code)
                            continue

                    except Exception:
                        ExperientialLabsModelManager.mark_model_failure(model_id, status_code=500)
                        logger.warning("ExperientialLabs model %s failed", model_id, exc_info=True)
                        continue

        # 4. Check for OpenRouter provider
        openrouter_provider = db.scalar(
            select(AIProvider).where(AIProvider.name == "openrouter", AIProvider.enabled == 1)
        )

        # 5. If OpenRouter is available, execute dynamic Free Model Quality Cascade
        if openrouter_provider:
            try:
                openrouter_base_url = validate_provider_base_url(openrouter_provider.base_url)
            except ValueError:
                logger.error("Disabled unsafe OpenRouter provider URL for provider %s", openrouter_provider.id)
                openrouter_provider.enabled = 0
                db.commit()
                openrouter_provider = None

        if openrouter_provider:
            active_key_tuple = ProviderRouter.select_active_key(db, openrouter_provider.id)
            if active_key_tuple:
                key_record, secret_key = active_key_tuple
                
                # Fetch free models sorted by quality score descending (highest quality first)
                ranked_free_models = await OpenRouterModelManager.get_ranked_candidates()

                # Try top 4 highest-quality candidates with snappy timeout (prevents long hangs)
                for candidate in ranked_free_models[:4]:
                    model_id = candidate["id"]
                    start_time = time.time()
                    logger.info(
                        "Trying OpenRouter model %s for agent %s (quality_score=%s)",
                        model_id,
                        agent_type,
                        candidate.get("quality_score"),
                    )

                    try:
                        url = f"{openrouter_base_url}/chat/completions"
                        headers = {
                            "Authorization": f"Bearer {secret_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://deckpilot.ai",
                            "X-Title": "deckpilotAI",
                        }
                        sys_prompt_final = system_prompt
                        if response_schema and "json" not in sys_prompt_final.lower():
                            sys_prompt_final += "\n\nRespond with valid JSON matching the requested structure."

                        payload: dict[str, Any] = {
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": sys_prompt_final},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.2,
                        }
                        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_read_timeout_seconds, connect=10.0)) as client:
                            resp = await client.post(url, headers=headers, json=payload)

                        latency = int((time.time() - start_time) * 1000)

                        if resp.status_code == 200:
                            resp_data = resp.json()
                            content = resp_data["choices"][0]["message"]["content"]
                            
                            parsed = _parse_llm_response(content, response_schema)

                            # Mark success on model and key
                            OpenRouterModelManager.mark_model_success(model_id)
                            key_record.last_used_at = now
                            key_record.failure_count = 0
                            db.commit()

                            # Record audit usage event
                            if user_id:
                                usage = UsageEvent(
                                    user_id=user_id,
                                    job_id=job_id,
                                    provider_id=openrouter_provider.id,
                                    key_id=key_record.id,
                                    model=model_id,
                                    event_type="generation",
                                    latency_ms=latency,
                                    success=1,
                                    created_at=now,
                                )
                                db.add(usage)
                                db.commit()

                            logger.info("OpenRouter model %s completed in %sms", model_id, latency)
                            return parsed

                        else:
                            # Model returned non-200 (e.g. 429 rate limit, 503 capacity limit, 500 error)
                            OpenRouterModelManager.mark_model_failure(model_id, status_code=resp.status_code)
                            logger.warning("OpenRouter model %s returned HTTP %s", model_id, resp.status_code)
                            continue  # Hand over context to next model in quality sequence!

                    except Exception:
                        OpenRouterModelManager.mark_model_failure(model_id, status_code=500)
                        logger.warning("OpenRouter model %s failed", model_id, exc_info=True)
                        continue  # Hand over context to next model in quality sequence!

        # 6. Fallback to other providers configured in database (Groq, Gemini, OpenAI, etc.)
        other_providers = db.scalars(
            select(AIProvider)
            .where(AIProvider.name.notin_(["openrouter", "experientiallabs"]), AIProvider.enabled == 1)
            .order_by(desc(AIProvider.priority))
        ).all()

        for provider in other_providers:
            try:
                provider_base_url = validate_provider_base_url(provider.base_url)
            except ValueError:
                logger.error("Skipping unsafe provider URL for provider %s", provider.id)
                provider.enabled = 0
                db.commit()
                continue

            key_tuple = ProviderRouter.select_active_key(db, provider.id)
            if not key_tuple:
                continue

            key_rec, secret_val = key_tuple
            p_name = provider.name.lower()
            if "groq" in p_name:
                model_name = "openai/gpt-oss-120b"
            elif "gemini" in p_name:
                model_name = settings.gemini_model
            elif "openai" in p_name:
                model_name = "gpt-4o-mini"
            elif "mistral" in p_name:
                model_name = "mistral-small-latest"
            else:
                model_name = "default"

            start_time = time.time()
            try:
                url = f"{provider_base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {secret_val}",
                    "Content-Type": "application/json",
                }
                sys_prompt_final = system_prompt
                if response_schema and "json" not in sys_prompt_final.lower():
                    sys_prompt_final += "\n\nRespond with valid JSON."

                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": sys_prompt_final},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                }
                if response_schema:
                    payload["response_format"] = {"type": "json_object"}

                async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_read_timeout_seconds, connect=10.0)) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    parsed = _parse_llm_response(content, response_schema)
                    latency = int((time.time() - start_time) * 1000)
                    key_rec.last_used_at = now
                    key_rec.failure_count = 0
                    db.commit()

                    if user_id:
                        usage = UsageEvent(
                            user_id=user_id,
                            job_id=job_id,
                            provider_id=provider.id,
                            key_id=key_rec.id,
                            model=model_name,
                            event_type="generation",
                            latency_ms=latency,
                            success=1,
                            created_at=now,
                        )
                        db.add(usage)
                        db.commit()

                    logger.info("Provider %s model %s completed in %sms", provider.name, model_name, latency)
                    return parsed
                logger.warning("Provider %s model %s returned HTTP %s", p_name, model_name, resp.status_code)
            except Exception:
                logger.warning("Provider %s failed", provider.name, exc_info=True)
                continue

        # Offline outlines are useful without configured providers. Do not mislabel
        # a quota failure or bad response as a successfully AI-written deck.
        if (openrouter_provider or other_providers) and agent_type in {"deck_planner", "slide_writer"}:
            raise RuntimeError("AI providers could not complete this stage. Check provider availability or quota, then retry.")
        return ProviderRouter._fallback_deterministic(agent_type, user_prompt)

    @staticmethod
    def _fallback_deterministic(agent_type: str, user_prompt: str) -> dict[str, Any]:
        """Provides deterministic fallback responses matching agent schemas when offline or in dev."""
        from app.services.design_system import default_brand, fallback_plan

        if agent_type == "deck_planner":
            return fallback_plan(user_prompt)
        if agent_type == "slide_writer":
            return {"slides": [], "generationMode": "offline_outline"}
        if agent_type == "font_brand_detection":
            return default_brand(user_prompt)
        return {"result": f"Completed {agent_type} successfully."}
