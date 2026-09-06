"""WebSocket endpoint for real-time orchestrator progress and streaming."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import AUTH_COOKIE_NAME
from app.db.engine import get_db
from app.services.auth_service import AuthService
from app.services.project_service import ProjectService
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/projects/{project_id}")
async def project_progress_websocket(
    websocket: WebSocket,
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Real-time WebSocket connection for project updates.
    Streams Claude Opus-style thinking, task states, slide-by-slide progress, and completion events.
    """
    auth_header = websocket.headers.get("authorization", "")
    scheme, _, header_token = auth_header.partition(" ")
    bearer_token = header_token.strip() if scheme.lower() == "bearer" else ""
    session_token = bearer_token or websocket.cookies.get(AUTH_COOKIE_NAME)
    if not session_token:
        await websocket.close(code=4401, reason="Authentication required")
        return

    current_user = AuthService.get_user_by_token(db, session_token)
    if not current_user:
        await websocket.close(code=4401, reason="Invalid or expired session")
        return

    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        await websocket.close(code=4403, reason="Access denied")
        return

    await ws_manager.connect(project_id, websocket)

    try:
        # Initial greeting and handshake confirmation
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
            "status": "ready",
            "message": "Connected to deckpilotAI real-time stream.",
        })

        while True:
            # Keep-alive / client message listener
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(project_id, websocket)
    except Exception:
        logger.warning("WebSocket connection failed for project %s", project_id, exc_info=True)
        await ws_manager.disconnect(project_id, websocket)
