"""Attachment schemas."""

from pydantic import BaseModel, Field


class AttachmentInitRequest(BaseModel):
    file_name: str
    mime_type: str
    byte_size: int = Field(gt=0, le=100 * 1024 * 1024)  # max 100MB
    sha256: str = Field(min_length=64, max_length=64)
    ownership_flag: str = Field(default="unknown", pattern="^(unknown|owned_or_authorized|third_party)$")


class AttachmentInitResponse(BaseModel):
    attachment_id: str
    upload_url: str | None = None
    storage_key: str


class AttachmentOut(BaseModel):
    id: str
    project_id: str
    message_id: str | None
    user_id: str
    file_name: str
    mime_type: str
    byte_size: int
    storage_key: str
    sha256: str
    status: str
    ownership_flag: str
    created_at: int

    model_config = {"from_attributes": True}
