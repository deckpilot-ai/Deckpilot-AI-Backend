import json
import logging
import re
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.rate_limit import action_rate_limiter
from app.db.engine import get_db
from app.models.deck import Artifact, DeckVersion
from app.models.job import AgentTask, GenerationJob
from app.models.user import User
from app.services.background_tasks import background_task_registry
from app.services.orchestrator import GenerationAlreadyRunningError, JobOrchestrator
from app.services.project_service import ProjectService
from app.services.storage import storage_service

router = APIRouter(tags=["generation"])
logger = logging.getLogger(__name__)


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(min_length=1, max_length=100_000)
    mode: Literal["generate", "revise", "export"] = "generate"
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey", min_length=8, max_length=64)
    background: bool = False


@router.post("/projects/{project_id}/jobs", status_code=status.HTTP_201_CREATED)
async def start_generation_job(
    project_id: str,
    req: CreateJobRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    retry_after = action_rate_limiter.check(
        f"generation:{current_user.id}",
        limit=20,
        window_seconds=60 * 60,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Generation rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        job, created = JobOrchestrator.create_job(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            mode=req.mode,
            idempotency_key=req.idempotency_key,
        )
    except GenerationAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not created:
        return {
            "job_id": job.id,
            "status": job.status,
            "mode": job.mode,
            "project_id": project_id,
        }

    if req.background:
        # Detached background execution: Runs independently of HTTP connection lifecycle
        background_task_registry.create(
            JobOrchestrator.run_job_background(
                job_id=job.id,
                user_prompt=req.prompt,
                user_id=current_user.id,
            )
        )
        return Response(
            content=json.dumps({
                "job_id": job.id,
                "status": "queued",
                "mode": job.mode,
                "project_id": project_id,
            }),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json",
        )

    # Synchronous execution
    updated_job = await JobOrchestrator.run_job(
        db=db,
        job_id=job.id,
        user_prompt=req.prompt,
        user_id=current_user.id,
    )

    return Response(
        content=json.dumps({
            "job_id": updated_job.id,
            "status": updated_job.status,
            "mode": updated_job.mode,
            "project_id": project_id,
        }),
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
    )


@router.post("/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_generation_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Verify project belongs to user
    project = ProjectService.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    cancelled_job = JobOrchestrator.cancel_job(db, job_id)
    return {
        "job_id": job_id,
        "status": cancelled_job.status if cancelled_job else "cancelled",
        "message": "Job cancelled successfully",
    }


@router.get("/projects/{project_id}/jobs/active")
def get_active_project_job(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Find currently running or queued job first
    job = db.scalar(
        select(GenerationJob)
        .where(
            GenerationJob.project_id == project_id,
            GenerationJob.status.in_(["queued", "running"]),
        )
        .order_by(desc(GenerationJob.created_at))
    )

    # If no active job, find the latest job for this project
    if not job:
        job = db.scalar(
            select(GenerationJob)
            .where(GenerationJob.project_id == project_id)
            .order_by(desc(GenerationJob.created_at))
        )

    if not job:
        return {"active": False, "job": None}

    tasks = db.scalars(select(AgentTask).where(AgentTask.job_id == job.id)).all()
    return {
        "active": job.status in ("queued", "running"),
        "job": {
            "id": job.id,
            "project_id": job.project_id,
            "status": job.status,
            "mode": job.mode,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "tasks": [
                {
                    "id": t.id,
                    "agent_type": t.agent_type,
                    "status": t.status,
                    "started_at": t.started_at,
                    "completed_at": t.completed_at,
                }
                for t in tasks
            ],
        },
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Verify project belongs to user
    project = ProjectService.get_project(db, job.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    tasks = db.scalars(select(AgentTask).where(AgentTask.job_id == job_id)).all()

    return {
        "id": job.id,
        "project_id": job.project_id,
        "status": job.status,
        "mode": job.mode,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "tasks": [
            {
                "id": t.id,
                "agent_type": t.agent_type,
                "status": t.status,
                "started_at": t.started_at,
                "completed_at": t.completed_at,
            }
            for t in tasks
        ],
    }


@router.get("/projects/{project_id}/decks/{version}")
def get_deck_version(
    project_id: str,
    version: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    deck_ver = db.scalar(
        select(DeckVersion).where(
            DeckVersion.project_id == project_id,
            DeckVersion.version == version,
        )
    )
    if not deck_ver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck version not found")

    deck_spec = {}
    if deck_ver.deck_json_artifact_id:
        art = db.scalar(select(Artifact).where(Artifact.id == deck_ver.deck_json_artifact_id))
        if art and art.json_data:
            deck_spec = json.loads(art.json_data)

    return {
        "version": deck_ver.version,
        "status": deck_ver.status,
        "created_at": deck_ver.created_at,
        "spec": deck_spec,
    }


@router.get("/projects/{project_id}/decks/{version}/download")
async def download_pptx(
    project_id: str,
    version: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    deck_ver = db.scalar(
        select(DeckVersion).where(
            DeckVersion.project_id == project_id,
            DeckVersion.version == version,
        )
    )
    if not deck_ver or not deck_ver.pptx_artifact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PPTX not available for this deck")

    art = db.scalar(select(Artifact).where(Artifact.id == deck_ver.pptx_artifact_id))
    if not art or not art.storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact storage key missing")

    try:
        file_bytes = await run_in_threadpool(storage_service.get_bytes, art.storage_key)
    except Exception as exc:
        logger.exception("Failed to load deck artifact %s", art.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Presentation storage is temporarily unavailable",
        ) from exc

    # 1. Prefer meaningful deckTitle from deck JSON artifact if available
    raw_title = (project.title or "Presentation").strip()
    if deck_ver.deck_json_artifact_id:
        json_art = db.scalar(select(Artifact).where(Artifact.id == deck_ver.deck_json_artifact_id))
        if json_art and json_art.json_data:
            try:
                deck_spec = json.loads(json_art.json_data)
                candidate_title = deck_spec.get("deckTitle")
                if candidate_title and isinstance(candidate_title, str) and len(candidate_title.strip()) > 2:
                    raw_title = candidate_title.strip()
            except Exception:
                pass

    # 2. Sanitize title: remove illegal filesystem characters (\/:*?"<>|), trailing periods/spaces
    sanitized = re.sub(r'[\/\\:\*\?"<>|\r\n\t]+', "", raw_title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip(". ")
    if not sanitized or len(sanitized) < 2:
        sanitized = "Presentation"
    sanitized = sanitized[:60].strip(". ")

    # 3. ASCII slug for legacy HTTP header compliance (RFC 2616)
    ascii_slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", sanitized).strip("._") or "Presentation"
    ascii_filename = f"{ascii_slug}_v{version}.pptx"

    # 4. RFC 5987 / RFC 6266 UTF-8 encoded filename for modern browsers
    utf8_filename = f"{sanitized}_v{version}.pptx"
    encoded_utf8 = quote(utf8_filename, safe="")

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_utf8}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
