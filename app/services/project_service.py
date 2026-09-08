"""Project management service."""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.deck import Artifact
from app.models.job import GenerationJob
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    @staticmethod
    def create_project(db: Session, user_id: str | User, req: ProjectCreate) -> Project:
        uid = user_id.id if isinstance(user_id, User) else str(user_id)
        project = Project(
            user_id=uid,
            title=req.title,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def list_projects(db: Session, user_id: str | User, skip: int = 0, limit: int = 50, is_admin: bool | None = None) -> list[Project]:
        uid = user_id.id if isinstance(user_id, User) else str(user_id)
        admin_flag = (getattr(user_id, "role", "") == "admin") if is_admin is None else is_admin
        stmt = select(Project)
        if not admin_flag:
            stmt = stmt.where(Project.user_id == uid)
        stmt = stmt.order_by(desc(Project.updated_at)).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_project(db: Session, project_id: str, user_id: str | User, is_admin: bool | None = None) -> Project | None:
        uid = user_id.id if isinstance(user_id, User) else str(user_id)
        admin_flag = (getattr(user_id, "role", "") == "admin") if is_admin is None else is_admin
        if admin_flag:
            stmt = select(Project).where(Project.id == project_id)
        else:
            stmt = select(Project).where(Project.id == project_id, Project.user_id == uid)
        return db.scalar(stmt)

    @staticmethod
    def update_project(db: Session, project_id: str, user_id: str | User, req: ProjectUpdate, is_admin: bool | None = None) -> Project | None:
        project = ProjectService.get_project(db, project_id, user_id, is_admin=is_admin)
        if not project:
            return None
        project.title = req.title
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete_project(db: Session, project_id: str, user_id: str | User, is_admin: bool | None = None) -> bool:
        project = ProjectService.get_project(db, project_id, user_id, is_admin=is_admin)
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True

    @staticmethod
    def has_active_job(db: Session, project_id: str) -> bool:
        return (
            db.scalar(
                select(GenerationJob.id).where(
                    GenerationJob.project_id == project_id,
                    GenerationJob.status.in_(("queued", "running")),
                )
            )
            is not None
        )

    @staticmethod
    def list_storage_keys(db: Session, project_id: str) -> list[str]:
        attachment_keys = db.scalars(
            select(Attachment.storage_key).where(Attachment.project_id == project_id)
        ).all()
        artifact_keys = db.scalars(
            select(Artifact.storage_key).where(
                Artifact.project_id == project_id,
                Artifact.storage_key.is_not(None),
            )
        ).all()
        return sorted({key for key in [*attachment_keys, *artifact_keys] if key})
