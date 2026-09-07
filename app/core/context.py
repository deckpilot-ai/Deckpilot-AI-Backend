"""Request and execution context tracking using Python contextvars."""

import uuid
from contextvars import ContextVar
from typing import Any

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
project_id_ctx: ContextVar[str | None] = ContextVar("project_id", default=None)
job_id_ctx: ContextVar[str | None] = ContextVar("job_id", default=None)


def generate_correlation_id() -> str:
    """Generate a standard production correlation ID (e.g. dp-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."""
    return f"dp-{uuid.uuid4()}"


def get_correlation_id() -> str:
    """Get active correlation ID from context or generate a fallback if none exists."""
    cid = correlation_id_ctx.get()
    if not cid:
        cid = generate_correlation_id()
        correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> Any:
    """Set the active correlation ID in context and return token."""
    if not correlation_id or not correlation_id.strip():
        correlation_id = generate_correlation_id()
    return correlation_id_ctx.set(correlation_id.strip())


def reset_correlation_id(token: Any) -> None:
    """Reset correlation ID context using token."""
    if token is not None:
        try:
            correlation_id_ctx.reset(token)
        except Exception:
            pass


def get_current_user_id() -> str | None:
    return user_id_ctx.get()


def set_current_user_id(user_id: str | None) -> None:
    user_id_ctx.set(user_id)


def get_current_project_id() -> str | None:
    return project_id_ctx.get()


def set_current_project_id(project_id: str | None) -> None:
    project_id_ctx.set(project_id)


def get_current_job_id() -> str | None:
    return job_id_ctx.get()


def set_current_job_id(job_id: str | None) -> None:
    job_id_ctx.set(job_id)


def capture_diagnostics_context() -> dict[str, Any]:
    """Capture current context variables as a clean dictionary."""
    return {
        "correlation_id": get_correlation_id(),
        "user_id": get_current_user_id(),
        "project_id": get_current_project_id(),
        "job_id": get_current_job_id(),
    }
