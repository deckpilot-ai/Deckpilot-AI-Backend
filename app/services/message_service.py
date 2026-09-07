"""Message service."""

import time

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.models.message import Message
from app.models.project import Project
from app.schemas.message import MessageCreate


class MessageService:
    @staticmethod
    def create_message(
        db: Session,
        project_id: str,
        user_id: str | None,
        req: MessageCreate,
    ) -> Message:
        message = Message(
            project_id=project_id,
            user_id=user_id if req.role == "user" else None,
            role=req.role,
            content=req.content,
        )
        db.add(message)
        db.flush()

        if req.attachment_ids:
            db.execute(
                update(Attachment)
                .where(Attachment.id.in_(req.attachment_ids), Attachment.project_id == project_id)
                .values(message_id=message.id)
            )

        # Update project updated_at
        project = db.scalar(select(Project).where(Project.id == project_id))
        if project:
            project.updated_at = int(time.time())

        db.commit()
        db.expire_all()
        loaded = db.scalar(
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.id == message.id)
        )
        return loaded or message

    @staticmethod
    def list_messages(
        db: Session,
        project_id: str,
        skip: int = 0,
        limit: int = 500,
    ) -> list[Message]:
        # Self-healing: link any unlinked attachments in this project to the first user message
        unlinked = db.scalars(
            select(Attachment).where(
                Attachment.project_id == project_id,
                Attachment.message_id.is_(None),
            )
        ).all()
        if unlinked:
            first_user_msg = db.scalar(
                select(Message)
                .where(Message.project_id == project_id, Message.role == "user")
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            if first_user_msg:
                for att in unlinked:
                    att.message_id = first_user_msg.id
                db.commit()
                db.expire_all()

        stmt = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.project_id == project_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

