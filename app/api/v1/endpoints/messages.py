"""Messages endpoints."""

import logging
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.rate_limit import action_rate_limiter
from app.db.engine import get_db
from app.models.attachment import Attachment
from app.models.deck import Artifact
from app.models.job import GenerationJob
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageEditRequest, MessageOut
from app.services.message_service import MessageService
from app.services.project_service import ProjectService
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/messages", tags=["messages"])


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    project_id: str,
    req: MessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageOut:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    message = MessageService.create_message(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        req=req,
    )
    return MessageOut.model_validate(message)


@router.get("", response_model=list[MessageOut])
def list_messages(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
) -> list[MessageOut]:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    messages = MessageService.list_messages(db, project_id, skip=skip, limit=limit)
    return [MessageOut.model_validate(m) for m in messages]


class DecisionQuestionOut(BaseModel):
    id: str
    question: str
    options: list[str]


class ChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=100_000)
    has_attachments: bool = False
    attachment_ids: list[str] = []
    mode: Literal["autopilot", "plan", "ask"] = "autopilot"


class ChatTurnResponse(BaseModel):
    intent: str
    mode: str = "autopilot"
    should_generate: bool
    user_message: MessageOut
    assistant_message: MessageOut | None = None
    plan_spec: dict[str, Any] | None = None
    decision_questions: list[DecisionQuestionOut] | None = None
    guardrail_info: dict[str, Any] | None = None


async def _execute_chat_turn(
    project_id: str,
    req: ChatTurnRequest,
    current_user: User,
    db: Session,
) -> ChatTurnResponse:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    retry_after = action_rate_limiter.check(
        f"chat:{current_user.id}",
        limit=60,
        window_seconds=60 * 60,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Chat rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    from app.services.chat_service import ChatService
    result = await ChatService.handle_chat_message(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        content=req.content,
        has_attachments=req.has_attachments,
        attachment_ids=req.attachment_ids,
        mode=req.mode,
    )
    return ChatTurnResponse(
        intent=result["intent"],
        mode=result.get("mode", req.mode),
        should_generate=result["should_generate"],
        user_message=MessageOut.model_validate(result["user_message"]),
        assistant_message=MessageOut.model_validate(result["assistant_message"]) if result.get("assistant_message") else None,
        plan_spec=result.get("plan_spec"),
        decision_questions=[DecisionQuestionOut(**dq) for dq in result["decision_questions"]] if result.get("decision_questions") else None,
        guardrail_info=result.get("guardrail_info"),
    )


@router.post("/{message_id}/edit", response_model=ChatTurnResponse, status_code=status.HTTP_200_OK)
async def edit_message(
    project_id: str,
    message_id: str,
    req: MessageEditRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatTurnResponse:
    project = ProjectService.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    target_msg = db.scalar(
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.id == message_id, Message.project_id == project_id)
    )
    if not target_msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if target_msg.role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only user messages can be edited")

    # 1. Remove requested attachments
    if req.removed_attachment_ids:
        for att_id in req.removed_attachment_ids:
            att = db.scalar(
                select(Attachment).where(
                    Attachment.id == att_id,
                    Attachment.project_id == project_id,
                )
            )
            if att:
                artifact_keys = db.scalars(
                    select(Artifact.storage_key).where(
                        Artifact.attachment_id == att.id,
                        Artifact.storage_key.is_not(None),
                    )
                ).all()
                storage_keys = sorted({att.storage_key, *(k for k in artifact_keys if k)})
                for s_key in storage_keys:
                    try:
                        await run_in_threadpool(storage_service.delete_object, s_key)
                    except Exception:
                        logger.warning("Failed to delete storage key %s", s_key, exc_info=True)
                db.delete(att)
        db.commit()

    # 2. Link any new attachments to this message
    if req.new_attachment_ids:
        db.execute(
            update(Attachment)
            .where(Attachment.id.in_(req.new_attachment_ids), Attachment.project_id == project_id)
            .values(message_id=target_msg.id)
        )
        db.commit()

    # 3. Truncate subsequent messages created after target message
    subsequent_messages = db.scalars(
        select(Message).where(
            Message.project_id == project_id,
            Message.id != target_msg.id,
            (Message.created_at > target_msg.created_at)
            | ((Message.created_at == target_msg.created_at) & (Message.id > target_msg.id)),
        )
    ).all()
    for sub_msg in subsequent_messages:
        db.delete(sub_msg)
    db.commit()

    # 4. Cancel active background generation job if running
    active_job = db.scalar(
        select(GenerationJob).where(
            GenerationJob.project_id == project_id,
            GenerationJob.status.in_(["queued", "running"]),
        )
    )
    if active_job:
        active_job.status = "cancelled"
        active_job.completed_at = int(time.time())
        db.commit()

    # 5. Fetch remaining attachments on target_msg
    remaining_att_ids = list(db.scalars(
        select(Attachment.id).where(
            Attachment.project_id == project_id,
            Attachment.message_id == target_msg.id,
        )
    ).all())
    has_attachments = len(remaining_att_ids) > 0

    # 6. Re-evaluate turn with edited message content & attachments
    from app.services.chat_service import ChatService
    result = await ChatService.handle_chat_message(
        db=db,
        project_id=project_id,
        user_id=current_user.id,
        content=req.content,
        has_attachments=has_attachments,
        attachment_ids=remaining_att_ids,
        mode=req.mode,
        existing_user_msg=target_msg,
    )
    return ChatTurnResponse(
        intent=result["intent"],
        mode=result.get("mode", req.mode),
        should_generate=result["should_generate"],
        user_message=MessageOut.model_validate(result["user_message"]),
        assistant_message=MessageOut.model_validate(result["assistant_message"]) if result.get("assistant_message") else None,
        plan_spec=result.get("plan_spec"),
        decision_questions=[DecisionQuestionOut(**dq) for dq in result["decision_questions"]] if result.get("decision_questions") else None,
        guardrail_info=result.get("guardrail_info"),
    )


chat_router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.post("/chat", response_model=ChatTurnResponse, status_code=status.HTTP_200_OK)
async def handle_chat_turn_messages(
    project_id: str,
    req: ChatTurnRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatTurnResponse:
    return await _execute_chat_turn(project_id, req, current_user, db)


@chat_router.post("", response_model=ChatTurnResponse, status_code=status.HTTP_200_OK)
async def handle_chat_turn_direct(
    project_id: str,
    req: ChatTurnRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatTurnResponse:
    return await _execute_chat_turn(project_id, req, current_user, db)

