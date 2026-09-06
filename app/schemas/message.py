"""Message schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentOut


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=100_000, description="Message content must not be empty")
    role: Literal["user"] = "user"
    attachment_ids: list[str] = []


class MessageOut(BaseModel):
    id: str
    project_id: str
    user_id: str | None
    role: str
    content: str
    created_at: int
    attachments: list[AttachmentOut] = []

    model_config = {"from_attributes": True}


class MessageEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=100_000, description="Message content must not be empty")
    removed_attachment_ids: list[str] = []
    new_attachment_ids: list[str] = []
    mode: Literal["autopilot", "plan", "ask"] = "autopilot"

