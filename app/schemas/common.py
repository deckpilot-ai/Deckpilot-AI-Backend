from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIErrorDetail(BaseModel):
    code: str
    message: str
    requestId: str | None = None
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: APIErrorDetail


class SuccessResponse(BaseModel, Generic[T]):
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)
