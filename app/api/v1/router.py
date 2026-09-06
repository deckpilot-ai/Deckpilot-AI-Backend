"""API v1 router registry."""

from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.attachments import router as attachments_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.generation import router as generation_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.messages import chat_router
from app.api.v1.endpoints.messages import router as messages_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(messages_router)
api_router.include_router(chat_router)
api_router.include_router(attachments_router)
api_router.include_router(generation_router)
api_router.include_router(admin_router)
api_router.include_router(ws_router)


