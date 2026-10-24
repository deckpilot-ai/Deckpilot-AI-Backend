"""Lifecycle-managed registry for in-process background work and scheduled health monitoring."""

import asyncio
from collections.abc import Coroutine
import logging
import socket
import time
from typing import Any
import uuid

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret
from app.models.job import AgentTask, GenerationJob
from app.models.provider import AIKey, AIProvider, AIProviderModel
from app.models.system_lock import SystemLock

logger = logging.getLogger(__name__)

HEALTH_PROBE_INTERVAL_SECONDS = 60
HEALTH_PROBE_TIMEOUT_SECONDS = 10.0
INSTANCE_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class BackgroundTaskRegistry:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def create(self, coroutine: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._completed)
        return task

    def _completed(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.error("Background task failed", exc_info=error)

    async def shutdown(self) -> None:
        if not self._tasks:
            return
        for task in tuple(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


background_task_registry = BackgroundTaskRegistry()


def fail_interrupted_jobs(db: Session) -> int:
    """Make jobs left by a terminated single-process worker safely retryable."""
    job_ids = list(
        db.scalars(
            select(GenerationJob.id).where(GenerationJob.status.in_(("queued", "running")))
        ).all()
    )
    if not job_ids:
        return 0

    completed_at = int(time.time())
    db.execute(
        update(AgentTask)
        .where(AgentTask.job_id.in_(job_ids), AgentTask.status.in_(("pending", "running")))
        .values(status="failed", error_code="worker_interrupted", completed_at=completed_at)
    )
    db.execute(
        update(GenerationJob)
        .where(GenerationJob.id.in_(job_ids))
        .values(status="permanently_failed", active_slot=None, completed_at=completed_at)
    )
    db.commit()
    logger.warning("Marked %s interrupted generation job(s) as failed", len(job_ids))
    return len(job_ids)


async def _probe_single_model(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    provider_name: str,
    base_url: str,
    api_key: str,
    model_id: str,
) -> tuple[str, str, int, float, str | None]:
    """Execute lightweight non-expensive probe ("Return exactly: OK") against an individual model."""
    async with semaphore:
        cleaned_url = base_url.rstrip("/")
        chat_url = f"{cleaned_url}/chat/completions"

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://deckpilot.ai",
            "X-Title": "deckpilotAI",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        effective_model_id = model_id.replace("models/", "") if provider_name == "gemini" else model_id
        payload = {
            "model": effective_model_id,
            "messages": [{"role": "user", "content": "Return exactly: OK"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }

        start = time.perf_counter()
        try:
            resp = await client.post(chat_url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start) * 1000
            err_msg = resp.text[:150] if resp.status_code != 200 else None
            return (provider_name, model_id, resp.status_code, latency_ms, err_msg)
        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start) * 1000
            return (provider_name, model_id, 504, latency_ms, "Timeout")
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return (provider_name, model_id, 503, latency_ms, str(exc)[:150])


async def execute_health_scan() -> dict[str, Any]:
    """Inspect all enabled AI providers & models, execute lightweight probes, and update rankings."""
    from app.core.network_security import validate_provider_base_url
    from app.db.engine import SessionLocal
    from app.services.health_tracker import health_tracker

    probe_targets: list[dict[str, Any]] = []
    all_candidate_dicts: list[dict[str, Any]] = []

    with SessionLocal() as db:
        # Check and ensure table exists if needed
        try:
            providers = db.scalars(select(AIProvider).where(AIProvider.enabled == 1)).all()
        except Exception:
            logger.warning("Unable to load providers for health check", exc_info=True)
            return {"scanned": 0, "healthy": 0}

        now_ts = int(time.time())
        for provider in providers:
            try:
                base_url = validate_provider_base_url(provider.base_url)
            except ValueError:
                continue

            # Find active key
            key_record = db.scalar(
                select(AIKey).where(
                    AIKey.provider_id == provider.id,
                    AIKey.enabled == 1,
                    (AIKey.cooldown_until == None) | (AIKey.cooldown_until <= now_ts),
                )
            )
            if not key_record:
                continue
            try:
                secret = decrypt_secret(key_record.encrypted_secret)
            except Exception:
                continue

            # Find all enabled models for this provider
            models = db.scalars(
                select(AIProviderModel).where(
                    AIProviderModel.provider_id == provider.id,
                    AIProviderModel.enabled == 1,
                )
            ).all()

            for m in models:
                candidate = {
                    "provider_name": provider.name,
                    "provider": provider,
                    "provider_base_url": base_url,
                    "key_record": key_record,
                    "secret_key": secret,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "base_priority": (provider.priority + m.priority) // 2,
                }
                all_candidate_dicts.append(candidate)

                # Check exponential backoff on previously failing models
                model_health = health_tracker._registry.get(f"{provider.name.lower()}::{m.model_id}")
                if model_health and model_health.backoff_cycles_remaining > 0:
                    model_health.backoff_cycles_remaining -= 1
                    logger.debug(
                        "Skipping probe for backoff candidate %s/%s (%d cycles left)",
                        provider.name, m.model_id, model_health.backoff_cycles_remaining,
                    )
                    continue

                probe_targets.append({
                    "provider_name": provider.name,
                    "base_url": base_url,
                    "api_key": secret,
                    "model_id": m.model_id,
                })

    if not probe_targets:
        if all_candidate_dicts:
            health_tracker.refresh_capability_rankings(all_candidate_dicts)
        return {"scanned": 0, "healthy": 0}

    # Bounded concurrency with asyncio.Semaphore
    semaphore = asyncio.Semaphore(8)
    req_timeout = httpx.Timeout(HEALTH_PROBE_TIMEOUT_SECONDS, connect=4.0)

    async with httpx.AsyncClient(timeout=req_timeout) as client:
        tasks = [
            _probe_single_model(
                semaphore=semaphore,
                client=client,
                provider_name=t["provider_name"],
                base_url=t["base_url"],
                api_key=t["api_key"],
                model_id=t["model_id"],
            )
            for t in probe_targets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    healthy_count = 0
    for r in results:
        if isinstance(r, Exception):
            continue
        pname, mid, status_code, latency_ms, err_msg = r
        health_tracker.record_probe_result(
            provider_name=pname,
            model_id=mid,
            status_code=status_code,
            latency_ms=latency_ms,
            error_msg=err_msg,
        )
        if status_code == 200:
            healthy_count += 1

    # Refresh capability rankings across all candidate models
    health_tracker.refresh_capability_rankings(all_candidate_dicts)

    logger.info(
        "60s Health Monitor completed: %d/%d models healthy across %d providers",
        healthy_count, len(probe_targets), len(set(t["provider_name"] for t in probe_targets)),
    )
    return {"scanned": len(probe_targets), "healthy": healthy_count}


async def start_health_probe_loop() -> None:
    """Background coroutine that executes a health scan every 60 seconds with distributed locking."""
    from app.db.engine import SessionLocal

    logger.info("Starting 60s LLM Health Monitor loop (instance=%s)", INSTANCE_ID)

    while True:
        try:
            # Distributed lock: only one backend instance executes the scan
            with SessionLocal() as db:
                locked = SystemLock.acquire(
                    db=db,
                    lock_name="llm_health_monitor",
                    locked_by=INSTANCE_ID,
                    lease_seconds=55,
                )

            if locked:
                await execute_health_scan()
            else:
                logger.debug("Health probe cycle skipped: lock currently held by another backend instance")

        except Exception:
            logger.warning("Health probe loop iteration encountered error", exc_info=True)

        await asyncio.sleep(HEALTH_PROBE_INTERVAL_SECONDS)


async def start_data_cleaner_loop() -> None:
    """Background coroutine that runs the document data cleaner policy with distributed locking."""
    from app.core.config import settings
    from app.db.engine import SessionLocal
    from app.services.data_cleaner import DataCleanerService

    if not settings.storage_cleaner_enabled:
        logger.info("Storage DataCleaner loop disabled in settings")
        return

    logger.info(
        "Starting Storage DataCleaner loop (retention=%d days, interval=%dh, instance=%s)",
        settings.storage_cleaner_retention_days,
        settings.storage_cleaner_interval_hours,
        INSTANCE_ID,
    )

    # Initial brief delay after startup to let app and db connections settle
    await asyncio.sleep(20)

    # Apply native R2 bucket lifecycle rules for scratch/tmp prefixes if R2 is configured
    try:
        DataCleanerService.apply_r2_bucket_lifecycle_configuration()
    except Exception as e:
        logger.debug("R2 lifecycle configuration notice: %s", e)

    interval_seconds = max(3600, settings.storage_cleaner_interval_hours * 3600)

    while True:
        try:
            with SessionLocal() as db:
                locked = SystemLock.acquire(
                    db=db,
                    lock_name="storage_data_cleaner",
                    locked_by=INSTANCE_ID,
                    lease_seconds=interval_seconds - 60,
                )

                if locked:
                    logger.info("Acquired storage_data_cleaner lock; executing data cleaner policy...")
                    report = await asyncio.to_thread(
                        DataCleanerService.run_cleanup_policy,
                        db=db,
                        retention_days=settings.storage_cleaner_retention_days,
                        dry_run=False,
                    )
                    logger.info(
                        "Storage DataCleaner run completed: pruned %s unused images, %s orphan objects, freed %s bytes",
                        report.get("unused_images_deleted", 0),
                        report.get("orphan_r2_objects_deleted", 0),
                        report.get("bytes_reclaimed", 0),
                    )
                else:
                    logger.debug("Storage DataCleaner cycle skipped: lock held by another instance")
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning("Storage DataCleaner loop iteration encountered error", exc_info=True)

        await asyncio.sleep(interval_seconds)

