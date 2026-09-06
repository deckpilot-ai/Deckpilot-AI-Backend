"""Multi-modal document and asset extraction agents.

Handles intake and parsing of PDF, Microsoft Word (.docx/.doc), Microsoft Excel (.xlsx/.xls),
CSV, and Images (JPG, PNG, WEBP), converting raw files into structured presentation artifacts.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.agents.base import Agent
from app.models.attachment import Attachment
from app.models.deck import Artifact
from app.services.extraction import DocumentExtractor, ExtractionResult
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class ReferenceIntakeAgent(Agent):
    """Agent responsible for document intake, file routing, and orchestrating extraction across all formats."""

    name: str = "reference_intake"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        project_id = context.get("project_id")
        db: Session | None = context.get("db")
        file_bytes: bytes | None = context.get("file_bytes")
        filename: str = context.get("filename", "document")
        mime_type: str = context.get("mime_type", "application/octet-stream")
        attachment_id: str | None = context.get("attachment_id")

        if file_bytes:
            extraction = DocumentExtractor.extract_document(file_bytes, filename, mime_type)
        elif db and project_id:
            # Batch process all pending attachments for the project
            stmt = select(Attachment).where(
                Attachment.project_id == project_id,
                Attachment.status.in_(["pending", "extracting"]),
            )
            pending_attachments = db.scalars(stmt).all()
            extraction = ExtractionResult()
            # If already processed, count existing artifacts
            existing_artifacts = db.scalars(
                select(Artifact).where(Artifact.project_id == project_id)
            ).all()
            return {
                "status": "success",
                "processed_count": len(pending_attachments),
                "total_artifacts": len(existing_artifacts),
            }
        else:
            return {"status": "skipped", "reason": "No document content provided"}

        # If DB and attachment are present, persist artifacts
        created_artifacts = []
        if db and project_id and attachment_id:
            stored_keys: list[str] = []
            try:
                for image_key, image_bytes, image_content_type in extraction.image_payloads:
                    await run_in_threadpool(
                        storage_service.put_bytes,
                        image_key,
                        image_bytes,
                        image_content_type,
                    )
                    stored_keys.append(image_key)

                # 1. Text blocks
                for tb in extraction.text_blocks:
                    art = Artifact(
                        project_id=project_id,
                        attachment_id=attachment_id,
                        type="text_block",
                        json_data=json.dumps(tb.get("content", "")),
                        source_locator=tb.get("source"),
                    )
                    db.add(art)
                    created_artifacts.append(art)

                # 2. Tables
                for tbl in extraction.tables:
                    art = Artifact(
                        project_id=project_id,
                        attachment_id=attachment_id,
                        type="table",
                        json_data=json.dumps(tbl),
                        source_locator=tbl.get("source"),
                    )
                    db.add(art)
                    created_artifacts.append(art)

                # 3. Images
                for img in extraction.extracted_images:
                    art = Artifact(
                        project_id=project_id,
                        attachment_id=attachment_id,
                        type="image",
                        storage_key=img.get("storage_key"),
                        json_data=json.dumps(img),
                        source_locator=img.get("source") or f"{filename}#page={img.get('page', 1)}",
                    )
                    db.add(art)
                    created_artifacts.append(art)

                db.commit()
            except Exception:
                db.rollback()
                for stored_key in stored_keys:
                    try:
                        await run_in_threadpool(storage_service.delete_object, stored_key)
                    except Exception:
                        logger.warning("Failed to clean up extracted image %s", stored_key, exc_info=True)
                raise

        return {
            "status": "success",
            "text_blocks_count": len(extraction.text_blocks),
            "tables_count": len(extraction.tables),
            "images_count": len(extraction.extracted_images),
            "metadata": extraction.metadata,
        }


class TextExtractionAgent(Agent):
    """Specialized agent for deep semantic parsing of PDF, Word, Excel, and CSV documents."""

    name: str = "text_extraction"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        file_bytes: bytes = context.get("file_bytes", b"")
        filename: str = context.get("filename", "document.txt")
        mime_type: str = context.get("mime_type", "text/plain")

        extraction = DocumentExtractor.extract_document(file_bytes, filename, mime_type)

        combined_text = "\n\n".join(tb["content"] for tb in extraction.text_blocks if "content" in tb)
        return {
            "status": "success",
            "filename": filename,
            "text_blocks": extraction.text_blocks,
            "tables": extraction.tables,
            "total_words": len(combined_text.split()),
            "metadata": extraction.metadata,
        }


class ImageExtractionAgent(Agent):
    """Specialized agent for image files (JPG, PNG, WEBP), asset indexing, and visual layout metadata."""

    name: str = "image_extraction"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        file_bytes: bytes = context.get("file_bytes", b"")
        filename: str = context.get("filename", "image.jpg")
        mime_type: str = context.get("mime_type", "image/jpeg")

        extraction = DocumentExtractor.extract_image(file_bytes, filename, mime_type)

        return {
            "status": "success",
            "filename": filename,
            "extracted_images": extraction.extracted_images,
            "text_blocks": extraction.text_blocks,
            "metadata": extraction.metadata,
        }
