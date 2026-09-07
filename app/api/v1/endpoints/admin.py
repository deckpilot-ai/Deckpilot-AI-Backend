import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.db.engine import get_db
from app.models.application_log import ApplicationLog
from app.models.provider import AIKey, AIProvider
from app.models.user import User
from app.schemas.application_log import (
    ApplicationLogDetailOut,
    ApplicationLogListResponse,
    ApplicationLogOut,
    ApplicationLogUpdateRequest,
)
from app.services.diagnostics_service import DiagnosticsService
from app.services.experientiallabs_models import ExperientialLabsModelManager
from app.services.openrouter_models import OpenRouterModelManager
from app.services.provider_router import ProviderRouter

router = APIRouter(prefix="/admin", tags=["admin"])


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    base_url: str = Field(min_length=8, max_length=512)
    provider_type: str = Field(default="openai_compatible", pattern=r"^openai_compatible$")
    priority: int = Field(default=1, ge=0, le=100)


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=128)
    secret: str = Field(min_length=8, max_length=4096)


class KeyRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: str = Field(min_length=8, max_length=4096)
    label: str | None = Field(default=None, min_length=1, max_length=128)


class RouteUpdate(BaseModel):
    candidates: list[dict[str, Any]] = Field(min_length=1, max_length=10)


@router.get("/providers")
def list_providers(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    # Synchronize environment providers first
    ProviderRouter.sync_environment_providers(db)

    providers = db.scalars(select(AIProvider).order_by(AIProvider.priority.desc())).all()
    result = []
    for p in providers:
        keys = db.scalars(select(AIKey).where(AIKey.provider_id == p.id)).all()
        result.append({
            "id": p.id,
            "name": p.name,
            "base_url": p.base_url,
            "provider_type": p.provider_type,
            "enabled": bool(p.enabled),
            "priority": p.priority,
            "keys": [
                {
                    "id": k.id,
                    "label": k.label,
                    "enabled": bool(k.enabled),
                    "cooldown_until": k.cooldown_until,
                    "failure_count": k.failure_count,
                    "last_used_at": k.last_used_at,
                    # Raw secret is NEVER returned!
                }
                for k in keys
            ],
        })
    return result


@router.get("/providers/status")
def get_providers_status(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """High-level status of AI providers and active free model cascade."""
    ProviderRouter.sync_environment_providers(db)
    providers = db.scalars(select(AIProvider).order_by(AIProvider.priority.desc())).all()

    openrouter_active = False
    explabs_active = False
    provider_summaries = []
    for p in providers:
        key_count = len(db.scalars(select(AIKey).where(AIKey.provider_id == p.id, AIKey.enabled == 1)).all())
        if p.name == "openrouter" and key_count > 0:
            openrouter_active = True
        elif p.name == "experientiallabs" and key_count > 0:
            explabs_active = True
        provider_summaries.append({
            "name": p.name,
            "base_url": p.base_url,
            "enabled": bool(p.enabled),
            "active_keys": key_count,
            "priority": p.priority,
        })

    model_overview = OpenRouterModelManager.get_status_overview()
    available_free_models = [m for m in model_overview if m["is_available"]]
    explabs_overview = ExperientialLabsModelManager.get_status_overview()

    return {
        "providers": provider_summaries,
        "openrouter_cascade_active": openrouter_active,
        "experientiallabs_cascade_active": explabs_active,
        "total_free_models_discovered": len(model_overview) + len(explabs_overview),
        "available_free_models_count": len(available_free_models) + len([m for m in explabs_overview if m["is_available"]]),
        "top_model": model_overview[0]["id"] if model_overview else None,
    }


@router.get("/providers/free-models")
async def get_free_models(
    admin: Annotated[User, Depends(require_admin)],
    provider: str = "all",
):
    """Returns the quality-ranked sequence of free models and their cooldown/health status."""
    await OpenRouterModelManager.fetch_free_models()
    await ExperientialLabsModelManager.fetch_free_models()

    if provider == "experientiallabs":
        models = ExperientialLabsModelManager.get_status_overview()
    elif provider == "openrouter":
        models = OpenRouterModelManager.get_status_overview()
    else:
        models = OpenRouterModelManager.get_status_overview() + ExperientialLabsModelManager.get_status_overview()

    return {
        "models": models,
        "total": len(models),
    }


@router.post("/providers/free-models/refresh")
async def refresh_free_models(
    admin: Annotated[User, Depends(require_admin)],
    provider: str = "all",
):
    """Forces an immediate re-fetch and re-ranking of all free models."""
    or_models = await OpenRouterModelManager.fetch_free_models(force_refresh=True)
    exp_models = await ExperientialLabsModelManager.fetch_free_models(force_refresh=True)

    if provider == "experientiallabs":
        return {
            "message": "Successfully refreshed ExperientialLabs free models",
            "total": len(exp_models),
            "top_model": exp_models[0]["id"] if exp_models else None,
        }
    return {
        "message": "Successfully refreshed OpenRouter and ExperientialLabs free models",
        "total": len(or_models) + len(exp_models),
        "top_model": or_models[0]["id"] if or_models else None,
    }


@router.post("/providers", status_code=status.HTTP_201_CREATED)
def create_provider(
    req: ProviderCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        provider = ProviderRouter.register_provider(
            db=db,
            name=req.name,
            base_url=req.base_url,
            provider_type=req.provider_type,
            priority=req.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return {"id": provider.id, "name": provider.name, "status": "created"}


@router.post("/providers/{provider_id}/keys", status_code=status.HTTP_201_CREATED)
def add_provider_key(
    provider_id: str,
    req: KeyCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    provider = db.scalar(select(AIProvider).where(AIProvider.id == provider_id))
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    try:
        key = ProviderRouter.add_key(db=db, provider_id=provider_id, label=req.label, secret=req.secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return {"id": key.id, "label": key.label, "status": "added"}


@router.put("/providers/{provider_id}/keys/{key_id}")
def rotate_provider_key(
    provider_id: str,
    key_id: str,
    req: KeyRotate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    key = db.scalar(select(AIKey).where(AIKey.id == key_id, AIKey.provider_id == provider_id))
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")
    try:
        key = ProviderRouter.rotate_key(db, key, req.secret, req.label)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return {"id": key.id, "label": key.label, "status": "rotated"}


@router.delete("/providers/{provider_id}/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_provider_key(
    provider_id: str,
    key_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    key = db.scalar(select(AIKey).where(AIKey.id == key_id, AIKey.provider_id == provider_id))
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")
    ProviderRouter.revoke_key(db, key)


@router.put("/routing/{agent_type}")
def set_agent_route(
    agent_type: str,
    req: RouteUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    route = ProviderRouter.set_agent_route(db=db, agent_type=agent_type, candidates=req.candidates)
    return {"agent_type": route.agent_type, "status": "updated"}


# ============================================================================
# Production Diagnostics & Application Logs Endpoints
# ============================================================================


@router.get("/logs", response_model=ApplicationLogListResponse)
def list_logs(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    correlation_id: str | None = None,
    level: str | None = None,
    service: str | None = None,
    agent_name: str | None = None,
    provider: str | None = None,
    environment: str | None = None,
    error_type: str | None = None,
    resolved: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Search and filter centralized production application logs."""
    stmt = select(ApplicationLog)
    conditions = []
    if search:
        s = f"%{search.strip()}%"
        conditions.append(
            or_(
                ApplicationLog.correlation_id.ilike(s),
                ApplicationLog.error_message.ilike(s),
                ApplicationLog.project_id.ilike(s),
                ApplicationLog.workspace_id.ilike(s),
                ApplicationLog.conversation_id.ilike(s),
                ApplicationLog.fingerprint.ilike(s),
                ApplicationLog.error_type.ilike(s),
                ApplicationLog.endpoint.ilike(s),
                ApplicationLog.agent_name.ilike(s),
            )
        )
    if correlation_id:
        conditions.append(ApplicationLog.correlation_id == correlation_id.strip())
    if level:
        conditions.append(ApplicationLog.level == level.strip().upper())
    if service:
        conditions.append(ApplicationLog.service == service.strip())
    if agent_name:
        conditions.append(ApplicationLog.agent_name == agent_name.strip())
    if provider:
        conditions.append(ApplicationLog.provider == provider.strip())
    if environment:
        conditions.append(ApplicationLog.environment == environment.strip())
    if error_type:
        conditions.append(ApplicationLog.error_type == error_type.strip())
    if resolved is not None:
        conditions.append(ApplicationLog.resolved == resolved)
    if start_time is not None:
        conditions.append(ApplicationLog.timestamp >= start_time)
    if end_time is not None:
        conditions.append(ApplicationLog.timestamp <= end_time)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # Count total matching
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Retrieve paginated items
    stmt = stmt.order_by(ApplicationLog.timestamp.desc()).offset(offset).limit(limit)
    items = db.scalars(stmt).all()

    return ApplicationLogListResponse(
        items=[ApplicationLogOut.model_validate(it) for it in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/{log_id}", response_model=ApplicationLogDetailOut)
def get_log_detail(
    log_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retrieve full diagnostic details for a specific log entry, including related request logs."""
    log_entry = db.scalar(select(ApplicationLog).where(ApplicationLog.id == log_id))
    if not log_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")

    # Fetch other logs sharing the same correlation_id
    related = db.scalars(
        select(ApplicationLog)
        .where(
            ApplicationLog.correlation_id == log_entry.correlation_id,
            ApplicationLog.id != log_entry.id,
        )
        .order_by(ApplicationLog.timestamp.asc())
    ).all()

    # Calculate count of similar error instances sharing the same fingerprint
    similar_count = 0
    if log_entry.fingerprint:
        similar_count = db.scalar(
            select(func.count(ApplicationLog.id)).where(ApplicationLog.fingerprint == log_entry.fingerprint)
        ) or 0

    detail_dict = {
        **{c.name: getattr(log_entry, c.name) for c in log_entry.__table__.columns},
        "related_logs": [ApplicationLogOut.model_validate(r) for r in related],
        "similar_instances_count": similar_count,
    }
    return ApplicationLogDetailOut.model_validate(detail_dict)


@router.patch("/logs/{log_id}", response_model=ApplicationLogOut)
def update_log_resolution(
    log_id: str,
    req: ApplicationLogUpdateRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update resolution status and investigator notes for a production log."""
    log_entry = db.scalar(select(ApplicationLog).where(ApplicationLog.id == log_id))
    if not log_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")

    log_entry.resolved = req.resolved
    if req.resolution_notes is not None:
        log_entry.resolution_notes = req.resolution_notes
    if req.resolved == 1:
        log_entry.resolved_at = int(time.time())
        log_entry.resolved_by = admin.id
    else:
        log_entry.resolved_at = None
        log_entry.resolved_by = None

    db.commit()
    db.refresh(log_entry)
    return ApplicationLogOut.model_validate(log_entry)


@router.post("/logs/cleanup")
def cleanup_logs(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Trigger log retention cleanup based on configured retention policies."""
    deleted = DiagnosticsService.cleanup_old_logs(
        db=db,
        error_retention_days=settings.log_retention_error_days,
        warning_retention_days=settings.log_retention_warning_days,
        resolved_retention_days=settings.log_retention_resolved_days,
    )
    return {
        "success": True,
        "deleted_count": deleted,
        "message": f"Cleaned up {deleted} old application logs.",
    }
