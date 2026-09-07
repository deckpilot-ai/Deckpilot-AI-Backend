"""Pydantic schemas for ApplicationLog diagnostics API."""

from pydantic import BaseModel, ConfigDict, Field


class ApplicationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    correlation_id: str
    fingerprint: str | None = None
    timestamp: int
    level: str
    environment: str
    service: str
    component: str | None = None
    agent_name: str | None = None
    operation: str | None = None
    endpoint: str | None = None
    http_method: str | None = None
    status_code: int | None = None

    # Context
    user_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    job_id: str | None = None

    # Error
    error_type: str | None = None
    error_message: str | None = None

    # External Provider
    provider: str | None = None
    provider_operation: str | None = None
    provider_status_code: int | None = None
    provider_request_id: str | None = None
    model_name: str | None = None

    # Execution metrics
    started_at: int | None = None
    completed_at: int | None = None
    duration_ms: int | None = None
    attempt_number: int | None = None
    max_attempts: int | None = None

    # Resolution
    resolved: int = 0
    resolution_notes: str | None = None
    resolved_at: int | None = None
    resolved_by: str | None = None


class ApplicationLogDetailOut(ApplicationLogOut):
    stack_trace: str | None = None
    request_data: str | None = None
    additional_context: str | None = None
    related_logs: list[ApplicationLogOut] = Field(default_factory=list)
    similar_instances_count: int = 0


class ApplicationLogListResponse(BaseModel):
    items: list[ApplicationLogOut]
    total: int
    limit: int
    offset: int


class ApplicationLogUpdateRequest(BaseModel):
    resolved: int = Field(ge=0, le=1)
    resolution_notes: str | None = None
