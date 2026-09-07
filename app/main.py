"""FastAPI application entry point for deckpilotAI."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.engine import SessionLocal, engine
from app.services.background_tasks import (
    background_task_registry,
    fail_interrupted_jobs,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail startup when the configured database is unavailable. Production
    # schema changes are applied explicitly through Alembic.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    if settings.app_env in {"development", "test"}:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        fail_interrupted_jobs(db)
    try:
        yield
    finally:
        await background_task_registry.shutdown()
        with SessionLocal() as db:
            fail_interrupted_jobs(db)


app = FastAPI(
    title="deckpilotAI API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def request_observability(request, call_next):
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 64 or not all(char.isalnum() or char in "-_" for char in request_id):
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request failure request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred", "request_id": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        round((time.perf_counter() - started) * 1000, 2),
    )
    return response

app.include_router(api_router, prefix=settings.api_v1_prefix)
