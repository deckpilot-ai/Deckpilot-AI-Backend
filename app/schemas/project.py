"""Project schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(default="Untitled Presentation", min_length=1, max_length=255)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)


class ProjectOut(BaseModel):
    id: str
    user_id: str
    title: str
    current_deck_version: int
    created_at: int
    updated_at: int

    model_config = {"from_attributes": True}
