"""Attachment upload and extraction endpoints."""

import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import action_rate_limiter
from app.db.engine import get_db
from app.models.attachment import Attachment
from app.models.deck import Artifact
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services.attachment_pipeline import PENDING_STATUSES, process_attachment
from app.services.background_tasks import background_task_registry
from app.services.project_service import ProjectService
from app.services.storage import storage_service
from app.services.upload_validation import (
    UploadValidationError,
    normalize_filename,
    validate_upload,
)

router = APIRouter(prefix="/projects/{project_id}/attachments", tags=["attachments"])
logger = logging.getLogger(__name__)


@router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AttachmentOut:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    retry_after = action_rate_limiter.check(
        f"upload:{current_user.id}",
        limit=30,
        window_seconds=60 * 60,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    chunks: list[bytes] = []
    byte_size = 0
    while chunk := await file.read(1024 * 1024):
        byte_size += len(chunk)
        if byte_size > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    try:
        filename = normalize_filename(file.filename)
        mime_type = await run_in_threadpool(validate_upload, file_bytes, filename, file.content_type)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    existing = db.scalar(select(Attachment).where(
        Attachment.project_id == project_id,
        Attachment.sha256 == sha256,
        Attachment.status.in_(("ready", *PENDING_STATUSES)),
    ))
    if existing:
        return AttachmentOut.model_validate(existing)

    # Store the original file only; extraction runs detached (see
    # attachment_pipeline) so this request returns before hosting proxies
    # such as Render's ~100s timeout cut the connection on large PDFs.
    storage_key = f"projects/{project_id}/attachments/{sha256[:16]}_{filename}"
    try:
        await run_in_threadpool(storage_service.put_bytes, storage_key, file_bytes, mime_type)
    except Exception as exc:
        logger.exception("Failed to store attachment for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage is temporarily unavailable",
        ) from exc

    attachment = Attachment(
        project_id=project_id,
        user_id=current_user.id,
        file_name=filename,
        mime_type=mime_type,
        byte_size=byte_size,
        storage_key=storage_key,
        sha256=sha256,
        status="pending",
        ownership_flag="unknown",
    )
    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except Exception as exc:
        db.rollback()
        try:
            await run_in_threadpool(storage_service.delete_object, storage_key)
        except Exception:
            logger.warning("Failed to clean up attachment object after database error", exc_info=True)
        logger.exception("Failed to persist attachment metadata for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachment metadata could not be saved",
        ) from exc

    background_task_registry.create(process_attachment(attachment.id))

    return AttachmentOut.model_validate(attachment)


@router.get("", response_model=list[AttachmentOut])
def list_attachments(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AttachmentOut]:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    stmt = select(Attachment).where(Attachment.project_id == project_id).order_by(Attachment.created_at.desc())
    attachments = db.scalars(stmt).all()
    return [AttachmentOut.model_validate(a) for a in attachments]


@router.get("/{attachment_id}", response_model=AttachmentOut)
def get_attachment(
    project_id: str,
    attachment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AttachmentOut:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    stmt = select(Attachment).where(Attachment.id == attachment_id, Attachment.project_id == project_id)
    attachment = db.scalar(stmt)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    return AttachmentOut.model_validate(attachment)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    project_id: str,
    attachment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    stmt = select(Attachment).where(Attachment.id == attachment_id, Attachment.project_id == project_id)
    attachment = db.scalar(stmt)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    artifact_keys = db.scalars(
        select(Artifact.storage_key).where(
            Artifact.attachment_id == attachment.id,
            Artifact.storage_key.is_not(None),
        )
    ).all()
    storage_keys = sorted({attachment.storage_key, *(key for key in artifact_keys if key)})
    for storage_key in storage_keys:
        try:
            await run_in_threadpool(storage_service.delete_object, storage_key)
        except Exception as exc:
            logger.exception("Failed to delete attachment object %s", attachment.id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage is temporarily unavailable",
            ) from exc

    db.delete(attachment)
    db.commit()
