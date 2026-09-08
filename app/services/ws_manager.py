"""WebSocket connection manager for real-time progress streaming."""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    def __init__(self) -> None:
        # Map of project_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock: asyncio.Lock | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._main_loop = loop

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def connect(self, project_id: str, websocket: WebSocket):
        try:
            self._main_loop = asyncio.get_running_loop()
        except Exception:
            pass
        await websocket.accept()
        async with self._get_lock():
            if project_id not in self._connections:
                self._connections[project_id] = set()
            self._connections[project_id].add(websocket)
        logger.info(f"[WebSocket] Client connected to project '{project_id}'. Total active: {len(self._connections[project_id])}")

    async def disconnect(self, project_id: str, websocket: WebSocket):
        async with self._get_lock():
            if project_id in self._connections:
                self._connections[project_id].discard(websocket)
                if not self._connections[project_id]:
                    del self._connections[project_id]
        logger.info(f"[WebSocket] Client disconnected from project '{project_id}'.")

    async def broadcast(self, project_id: str, event: dict[str, Any]):
        """Broadcasts a JSON-serializable event to all clients connected to project_id."""
        if project_id not in self._connections:
            return

        targets = list(self._connections.get(project_id, set()))
        if not targets:
            return

        message_str = json.dumps(event)
        disconnected = []

        for ws in targets:
            try:
                await ws.send_text(message_str)
            except Exception:
                logger.warning("WebSocket send failed for project %s", project_id, exc_info=True)
                disconnected.append(ws)

        if disconnected:
            async with self._get_lock():
                for ws in disconnected:
                    if project_id in self._connections:
                        self._connections[project_id].discard(ws)

    def broadcast_sync(self, project_id: str, event: dict[str, Any]):
        """Thread-safe wrapper to broadcast events from any thread without blocking."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(project_id, event))
        except RuntimeError:
            if self._main_loop and self._main_loop.is_running():
                try:
                    asyncio.run_coroutine_threadsafe(self.broadcast(project_id, event), self._main_loop)
                except Exception:
                    pass


ws_manager = WebSocketConnectionManager()
