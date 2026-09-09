"""Asynchronous attachment extraction pipeline.

The upload endpoint returns as soon as the raw file is validated and stored
(``status="pending"``); the CPU-heavy document extraction runs as a detached
background task. This keeps upload requests well under hosting proxy timeouts
(e.g. Render's ~100 second limit) where synchronous extraction of large PDFs
would otherwise be killed mid-request.

Status lifecycle: pending -> extracting -> ready | failed
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.models.attachment import Attachment
from app.models.deck import Artifact
from app.services.extraction import DocumentExtractor
from app.services.storage import storage_service
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("pending", "extracting")

# Mirrors JobOrchestrator's injectable session factory so tests can point the
# detached pipeline at the test database.
_session_factory: sessionmaker | None = None


def set_session_factory(factory: sessionmaker) -> None:
    """Override the session factory used for detached background runs."""
    global _session_factory
    _session_factory = factory


def get_session_factory() -> sessionmaker:
    if _session_factory is not None:
        return _session_factory
    from app.db.engine import SessionLocal

    return SessionLocal


async def process_attachment(attachment_id: str, db: Session | None = None) -> None:
    """Extract one pending attachment into artifacts.

    Idempotent and safe to re-run: originals are re-read from object storage,
    extracted images are stored under deterministic keys (overwrite), and
    artifacts are written in a single final transaction together with the
    ``ready`` status flip.

    When ``db`` is provided the caller owns the session/transaction (used by
    the orchestrator's inline fallback); otherwise a dedicated session from
    the session factory is opened (background task path).
    """
    if db is not None:
        await _process_with_session(db, attachment_id)
        return
    factory = get_session_factory()
    session = factory()
    try:
        await _process_with_session(session, attachment_id)
    finally:
        session.close()


async def _process_with_session(db: Session, attachment_id: str) -> None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.status == "ready":
        return



    if attachment.status != "extracting":
        attachment.status = "extracting"
        db.commit()

    project_id = attachment.project_id
    filename = attachment.file_name
    mime_type = attachment.mime_type
    sha_prefix = attachment.sha256[:16]

    try:
        def progress_callback(msg: str) -> None:
            try:
                ws_manager.broadcast_sync(
                    project_id,
                    {
                        "type": "attachment_progress",
                        "project_id": project_id,
                        "attachment_id": attachment_id,
                        "filename": filename,
                        "message": msg,
                    },
                )
                ws_manager.broadcast_sync(
                    project_id,
                    {
                        "type": "agent_task",
                        "project_id": project_id,
                        "agent_type": "reference_intake",
                        "status": "running",
                        "message": msg,
                    },
                )
            except Exception:
                logger.debug("Failed broadcasting extraction progress", exc_info=True)

        file_bytes = await run_in_threadpool(storage_service.get_bytes, attachment.storage_key)
        extraction = await run_in_threadpool(
            DocumentExtractor.extract_document, file_bytes, filename, mime_type, progress_callback
        )

        key_map = {
            key: f"projects/{project_id}/attachments/{sha_prefix}/assets/{key.rsplit('/', 1)[-1]}"
            for key, _, _ in extraction.image_payloads
        }
        extraction.image_payloads = [
            (key_map[key], data, content_type)
            for key, data, content_type in extraction.image_payloads
        ]
        for img in extraction.extracted_images:
            img["storage_key"] = key_map[img["storage_key"]]
        extracted_storage_keys = [key for key, _data, _content_type in extraction.image_payloads]

        if extraction.image_payloads:
            progress_callback(f"Storing {len(extraction.image_payloads)} extracted visual assets from {filename}...")

        try:
            semaphore = asyncio.Semaphore(2)

            async def store_image(image_key: str, image_bytes: bytes, image_content_type: str) -> None:
                async with semaphore:
                    await run_in_threadpool(
                        storage_service.put_bytes, image_key, image_bytes, image_content_type
                    )

            results = await asyncio.gather(
                *(store_image(*payload) for payload in extraction.image_payloads),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
        except Exception:
            for stored_key in extracted_storage_keys:
                try:
                    await run_in_threadpool(storage_service.delete_object, stored_key)
                except Exception:
                    logger.warning("Failed to clean up extracted image", exc_info=True)
            raise

        try:
            artifacts_to_add = []
            for tb in extraction.text_blocks:
                artifacts_to_add.append(
                    Artifact(
                        project_id=project_id,
                        attachment_id=attachment.id,
                        type="text_block",
                        json_data=json.dumps(tb.get("content", "")),
                        source_locator=tb.get("source"),
                    )
                )
            for tbl in extraction.tables:
                artifacts_to_add.append(
                    Artifact(
                        project_id=project_id,
                        attachment_id=attachment.id,
                        type="table",
                        json_data=json.dumps(tbl),
                        source_locator=tbl.get("source"),
                    )
                )
            for img in extraction.extracted_images:
                artifacts_to_add.append(
                    Artifact(
                        project_id=project_id,
                        attachment_id=attachment.id,
                        type="image",
                        storage_key=img.get("storage_key"),
                        json_data=json.dumps(img),
                        source_locator=img.get("source") or f"{filename}#page={img.get('page', 1)}",
                    )
                )
            if artifacts_to_add:
                db.add_all(artifacts_to_add)
            attachment.status = "ready"
            db.commit()

            pages_count = extraction.metadata.get("page_count", 1)
            img_count = len(extraction.extracted_images)
            progress_callback(
                f"Completed extraction for {filename}: {pages_count} pages processed, {img_count} high-res visual figures captured."
            )
        except Exception:
            db.rollback()
            raise
    except Exception:
        logger.exception("Attachment extraction failed attachment_id=%s", attachment_id)
        db.rollback()
        try:
            attachment = db.get(Attachment, attachment_id)
            if attachment is not None and attachment.status != "ready":
                attachment.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to mark attachment %s as failed", attachment_id)


async def wait_for_pending_attachments(
    db: Session,
    project_id: str,
    *,
    timeout_seconds: float = 60.0,
    poll_interval: float = 1.0,
    emit: Callable[..., None] | None = None,
) -> None:
    """Block until this project has no attachments still being extracted.

    Used by the orchestrator's reference_intake stage so a generation job that
    starts right after an upload always runs with complete grounding data.
    """
    # 1. Process any pending attachments inline if not yet picked up
    pending = db.scalars(
        select(Attachment).where(
            Attachment.project_id == project_id, Attachment.status == "pending"
        )
    ).all()
    pending_ids = [att.id for att in pending]

    for att_id in pending_ids:
        if emit is not None:
            emit("reference_intake", "running", "Processing attached document...")
        try:
            await process_attachment(att_id, db=db)
        except Exception:
            logger.warning("Inline attachment processing failed for attachment %s", att_id, exc_info=True)

    # 2. Wait for any actively extracting attachments to finish
    deadline = time.monotonic() + timeout_seconds
    while True:
        extracting_count = db.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(Attachment.project_id == project_id, Attachment.status == "extracting")
        ) or 0
        if not extracting_count:
            return
        if time.monotonic() >= deadline:
            break
        if emit is not None:
            emit(
                "reference_intake",
                "running",
                f"Extracting {extracting_count} reference document(s)...",
            )
        await asyncio.sleep(poll_interval)



