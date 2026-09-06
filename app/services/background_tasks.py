"""Lifecycle-managed registry for in-process background work."""

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.job import AgentTask, GenerationJob

logger = logging.getLogger(__name__)


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
