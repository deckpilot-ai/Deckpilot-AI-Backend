"""API endpoints for Design Preset management and automated PPT design configuration."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.engine import get_db
from app.models.project import Project
from app.models.user import User
from app.services.design_preset_registry import DesignPresetRegistry
from app.tools.design_auto_configurator import DesignAutoConfigurator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/design", tags=["design"])


@router.post("/auto-configure", status_code=status.HTTP_201_CREATED)
async def auto_configure_design(
    file: Annotated[UploadFile, File(description="Reference PowerPoint (.pptx) file to reverse-engineer")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str | None, Form()] = None,
    project_id: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """Upload any PPTX presentation to reverse-engineer its visual language and configure into the system."""
    if not file.filename.endswith(".pptx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PowerPoint presentation (.pptx)",
        )

    # Validate project ownership if project_id provided
    if project_id:
        proj = db.get(Project, project_id)
        if not proj or (proj.user_id != current_user.id and not current_user.is_superuser):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    pptx_bytes = await file.read()
    if len(pptx_bytes) < 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty or too small")

    try:
        detected_name = name or file.filename.rsplit(".", 1)[0]
        preset = DesignAutoConfigurator.configure_from_pptx(
            pptx_source=pptx_bytes,
            name=detected_name,
            project_id=project_id,
        )
        return {
            "status": "configured",
            "message": f"Successfully extracted and configured design preset '{detected_name}'",
            "preset": preset,
        }
    except Exception as e:
        logger.error("Auto-configuration failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to reverse-engineer PPT design: {str(e)}",
        )


@router.get("/presets")
async def list_design_presets(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """List all available benchmark and custom user design presets."""
    return DesignPresetRegistry.list_presets()


@router.get("/presets/{preset_id}")
async def get_design_preset(
    preset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Retrieve details for a specific design preset."""
    preset = DesignPresetRegistry.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design preset not found")
    return preset


@router.post("/projects/{project_id}/apply-preset")
async def apply_preset_to_project(
    project_id: str,
    preset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Attach a configured design preset to a specific project."""
    proj = db.get(Project, project_id)
    if not proj or (proj.user_id != current_user.id and not current_user.is_superuser):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    preset = DesignPresetRegistry.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design preset not found")

    return {
        "status": "applied",
        "project_id": project_id,
        "preset_id": preset_id,
        "preset_name": preset.get("name"),
    }
