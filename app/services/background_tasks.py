"""Lifecycle-managed registry for in-process background work."""

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret
from app.models.job import AgentTask, GenerationJob
from app.models.provider import AIKey, AIProvider

logger = logging.getLogger(__name__)

# Health probe configuration
HEALTH_PROBE_INTERVAL_SECONDS = 60
HEALTH_PROBE_TIMEOUT_SECONDS = 8.0


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


async def _probe_single_provider(
    provider_name: str,
    base_url: str,
    api_key: str,
) -> tuple[str, float | None, bool]:
    """Probe a single provider's /models endpoint. Returns (name, latency_ms, success)."""
    cleaned_url = base_url.rstrip("/")
    # Determine models endpoint
    models_url = f"{cleaned_url}/models"

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://deckpilot.ai",
        "X-Title": "deckpilotAI",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        start = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(HEALTH_PROBE_TIMEOUT_SECONDS, connect=4.0)
        ) as client:
            resp = await client.get(models_url, headers=headers)
        latency_ms = (time.perf_counter() - start) * 1000

        if resp.status_code == 200:
            return (provider_name, latency_ms, True)
        else:
            logger.debug(
                "Health probe %s returned HTTP %s",
                provider_name,
                resp.status_code,
            )
            return (provider_name, latency_ms, False)
    except Exception as exc:
        logger.debug("Health probe %s failed: %s", provider_name, exc)
        return (provider_name, None, False)


async def start_health_probe_loop() -> None:
    """Background coroutine that probes all enabled providers every HEALTH_PROBE_INTERVAL_SECONDS.

    Runs indefinitely until cancelled. Records results in the HealthTracker
    so the adaptive router always has fresh latency and availability data.
    """
    # Import here to avoid circular imports
    from app.core.network_security import validate_provider_base_url
    from app.db.engine import SessionLocal
    from app.services.health_tracker import health_tracker

    logger.info(
        "Starting health probe loop (interval=%ds)",
        HEALTH_PROBE_INTERVAL_SECONDS,
    )

    while True:
        try:
            # Collect enabled providers and their keys
            probe_targets: list[tuple[str, str, str]] = []
            with SessionLocal() as db:
                providers = db.scalars(
                    select(AIProvider).where(AIProvider.enabled == 1)
                ).all()
                for provider in providers:
                    try:
                        base_url = validate_provider_base_url(provider.base_url)
                    except ValueError:
                        continue

                    # Find first active key
                    now_ts = int(time.time())
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

                    probe_targets.append((provider.name, base_url, secret))

            if probe_targets:
                # Probe all providers concurrently
                tasks = [
                    _probe_single_provider(name, url, key)
                    for name, url, key in probe_targets
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.debug("Probe task exception: %s", result)
                        continue
                    pname, latency_ms, success = result
                    health_tracker.record_probe(pname, latency_ms, success)

                healthy = sum(
                    1 for r in results if not isinstance(r, Exception) and r[2]
                )
                logger.info(
                    "Health probes complete: %d/%d providers healthy",
                    healthy,
                    len(probe_targets),
                )

        except Exception:
            logger.warning("Health probe loop iteration failed", exc_info=True)

        await asyncio.sleep(HEALTH_PROBE_INTERVAL_SECONDS)

