"""Common Pydantic models for API responses and errors."""

from typing import Any

from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    code: str
    message: str
    requestId: str | None = None
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: APIErrorDetail


class SuccessResponse[T](BaseModel):
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)
