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
from app.core.context import (
    generate_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from app.db.base import Base
from app.db.engine import SessionLocal, engine
from app.services.background_tasks import (
    background_task_registry,
    fail_interrupted_jobs,
)
from app.services.diagnostics_service import DiagnosticsService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register main event loop for safe multi-thread WebSocket broadcasting
    import asyncio
    from app.services.ws_manager import ws_manager
    try:
        ws_manager.set_main_loop(asyncio.get_running_loop())
    except Exception:
        pass

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
    expose_headers=["Content-Disposition", "X-Correlation-ID", "X-Request-ID"],
)


@app.middleware("http")
async def request_observability(request, call_next):
    raw_cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id", "")
    if raw_cid and len(raw_cid) <= 64 and all(char.isalnum() or char in "-_" for char in raw_cid):
        correlation_id = raw_cid
    else:
        correlation_id = generate_correlation_id()

    token = set_correlation_id(correlation_id)
    request.state.correlation_id = correlation_id
    request.state.request_id = correlation_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(
            "Unhandled request failure correlation_id=%s method=%s path=%s",
            correlation_id,
            request.method,
            request.url.path,
        )
        DiagnosticsService.log_exception(
            exc=exc,
            endpoint=request.url.path,
            http_method=request.method,
            status_code=500,
            correlation_id=correlation_id,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "An unexpected error occurred.",
                "error_id": correlation_id,
                "detail": "An unexpected error occurred",
                "request_id": correlation_id,
            },
        )
    finally:
        reset_correlation_id(token)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    # Check for slow operation
    if (
        int(duration_ms) > settings.slow_api_threshold_ms
        and request.url.path not in ("/api/v1/health", "/docs", "/openapi.json", "/redoc")
    ):
        DiagnosticsService.log_slow_operation(
            component="api",
            operation=f"{request.method} {request.url.path}",
            duration_ms=int(duration_ms),
            threshold_ms=settings.slow_api_threshold_ms,
            correlation_id=correlation_id,
            endpoint=request.url.path,
            http_method=request.method,
            status_code=response.status_code,
        )

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Request-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    logger.info(
        "request_complete correlation_id=%s method=%s path=%s status=%s duration_ms=%s",
        correlation_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

app.include_router(api_router, prefix=settings.api_v1_prefix)
