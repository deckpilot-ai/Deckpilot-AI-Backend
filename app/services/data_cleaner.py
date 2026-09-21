"""Data cleaner policy for user document storage optimization (Cloudflare R2 & Local Storage).

Policy Details:
- Deletes unused data from user documents (such as extracted figures, intermediate
  image assets, and orphan objects) older than a configurable retention threshold (default 3 days).
- Intelligently preserves all images and assets that are actively referenced in any generated
  presentation slide (DeckVersion / deck_json).
- Preserves all data newer than the retention threshold (default 3 days).
- Reclaims Cloudflare R2 bucket storage and prunes stale database artifact records.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deck import Artifact, DeckVersion
from app.models.job import GenerationJob
from app.services.diagnostics_service import DiagnosticsService
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class DataCleanerReport:
    def __init__(
        self,
        retention_days: int,
        cutoff_timestamp: int,
        dry_run: bool,
    ) -> None:
        self.timestamp: int = int(time.time())
        self.retention_days: int = retention_days
        self.cutoff_timestamp: int = cutoff_timestamp
        self.dry_run: bool = dry_run
        self.scanned_artifacts: int = 0
        self.used_images_preserved: int = 0
        self.unused_images_deleted: int = 0
        self.orphan_r2_objects_deleted: int = 0
        self.database_records_pruned: int = 0
        self.bytes_reclaimed: int = 0
        self.deleted_storage_keys: list[str] = []
        self.duration_seconds: float = 0.0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iso_time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "retention_days": self.retention_days,
            "cutoff_timestamp": self.cutoff_timestamp,
            "dry_run": self.dry_run,
            "scanned_artifacts": self.scanned_artifacts,
            "used_images_preserved": self.used_images_preserved,
            "unused_images_deleted": self.unused_images_deleted,
            "orphan_r2_objects_deleted": self.orphan_r2_objects_deleted,
            "database_records_pruned": self.database_records_pruned,
            "bytes_reclaimed": self.bytes_reclaimed,
            "bytes_reclaimed_mb": round(self.bytes_reclaimed / (1024 * 1024), 2),
            "deleted_storage_keys": self.deleted_storage_keys,
            "sample_deleted_keys": self.deleted_storage_keys[:20],
            "duration_seconds": round(self.duration_seconds, 3),
            "errors": self.errors,
            "status": "success" if not self.errors else "completed_with_errors",
        }


class DataCleanerService:
    """Manages storage optimization and lifecycle data cleaning for user documents."""

    _last_report: dict[str, Any] | None = None

    @classmethod
    def get_last_report(cls) -> dict[str, Any] | None:
        return cls._last_report

    @classmethod
    def get_used_asset_identifiers(cls, db: Session) -> tuple[set[str], set[str]]:
        """Identify all visual assets currently referenced in active presentation decks.

        Returns:
            A tuple of (used_artifact_ids, used_storage_keys)
        """
        used_artifact_ids: set[str] = set()
        used_storage_keys: set[str] = set()

        # 1. Inspect all deck_json artifacts to extract referenced image IDs and storage keys
        deck_json_stmt = select(Artifact.json_data).where(
            Artifact.type == "deck_json",
            Artifact.json_data.isnot(None),
        )
        for json_str in db.scalars(deck_json_stmt).all():
            if not json_str:
                continue
            try:
                data = json.loads(json_str)
                # Parse slides array
                slides = []
                if isinstance(data, dict):
                    slides = data.get("slides") or []
                elif isinstance(data, list):
                    slides = data

                for slide in slides:
                    if not isinstance(slide, dict):
                        continue
                    # Check all common slide image reference keys
                    img_id = (
                        slide.get("image_artifact_id")
                        or slide.get("imageArtifactId")
                        or slide.get("imageId")
                    )
                    if img_id:
                        used_artifact_ids.add(str(img_id).strip())

                    img_key = (
                        slide.get("storage_key")
                        or slide.get("storageKey")
                        or slide.get("image_path")
                        or slide.get("imagePath")
                    )
                    if img_key and isinstance(img_key, str) and not img_key.startswith("http"):
                        used_storage_keys.add(img_key.strip())

                    # Check structured image_refs list
                    for ref in slide.get("image_refs", []):
                        if isinstance(ref, dict):
                            if ref.get("artifact_id"):
                                used_artifact_ids.add(str(ref["artifact_id"]).strip())
                            if ref.get("storage_key"):
                                used_storage_keys.add(str(ref["storage_key"]).strip())
                        elif isinstance(ref, str):
                            used_artifact_ids.add(ref.strip())
            except Exception as e:
                logger.debug("Error parsing deck_json artifact for used images: %s", e)

        # 2. Protect assets from any currently active or queued generation jobs
        active_job_stmt = select(GenerationJob.id).where(
            GenerationJob.status.in_(["queued", "running"])
        )
        active_job_ids = set(db.scalars(active_job_stmt).all())
        if active_job_ids:
            active_job_art_stmt = select(Artifact.id, Artifact.storage_key).where(
                Artifact.job_id.in_(active_job_ids)
            )
            for art_id, s_key in db.execute(active_job_art_stmt).all():
                if art_id:
                    used_artifact_ids.add(str(art_id))
                if s_key:
                    used_storage_keys.add(str(s_key))

        # 3. Protect pptx export files
        pptx_stmt = select(Artifact.storage_key).where(
            Artifact.type == "pptx",
            Artifact.storage_key.isnot(None),
        )
        for s_key in db.scalars(pptx_stmt).all():
            if s_key:
                used_storage_keys.add(str(s_key))

        return used_artifact_ids, used_storage_keys

    @classmethod
    def run_cleanup_policy(
        cls,
        db: Session,
        retention_days: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Execute the 3-day data cleaner policy on Cloudflare R2 and database artifacts.

        Args:
            db: Active SQLAlchemy Session
            retention_days: Age cutoff in days (default from settings or 3 days)
            dry_run: If True, computes metrics without deleting data

        Returns:
            Dictionary containing cleanup metrics and reclaimed storage statistics
        """
        start_time = time.perf_counter()
        days = retention_days if retention_days is not None else settings.storage_cleaner_retention_days
        days = max(1, days)
        cutoff_timestamp = int(time.time()) - (days * 86400)

        report = DataCleanerReport(
            retention_days=days,
            cutoff_timestamp=cutoff_timestamp,
            dry_run=dry_run,
        )

        try:
            # 1. Discover all actively used presentation images
            used_artifact_ids, used_storage_keys = cls.get_used_asset_identifiers(db)

            # 2. Query all document image artifacts older than retention threshold
            # Target extracted document figures, preview thumbnails, and intermediate artifacts
            candidate_stmt = select(Artifact).where(
                Artifact.created_at <= cutoff_timestamp,
                Artifact.type.in_(["image", "slide_preview", "table_image"]),
            )
            candidate_artifacts = list(db.scalars(candidate_stmt).all())
            report.scanned_artifacts = len(candidate_artifacts)

            artifacts_to_delete: list[Artifact] = []
            keys_to_delete: list[str] = []

            for art in candidate_artifacts:
                art_id = str(art.id).strip()
                s_key = (art.storage_key or "").strip()

                # Preserve if actively referenced in any presentation slide
                if art_id in used_artifact_ids or (s_key and s_key in used_storage_keys):
                    report.used_images_preserved += 1
                    continue

                artifacts_to_delete.append(art)
                if s_key:
                    keys_to_delete.append(s_key)

            report.unused_images_deleted = len(artifacts_to_delete)

            # 3. Detect and sweep orphan objects in Cloudflare R2 / Object Storage
            # (Objects older than retention threshold under extracted/ with no active artifact record)
            try:
                storage_objects = storage_service.list_objects(prefix="extracted/")
                all_active_keys_stmt = select(Artifact.storage_key).where(
                    Artifact.storage_key.isnot(None)
                )
                active_db_keys = set(db.scalars(all_active_keys_stmt).all())

                cutoff_dt = datetime.fromtimestamp(cutoff_timestamp, tz=timezone.utc)
                orphan_keys: list[str] = []

                for obj in storage_objects:
                    obj_key = obj.get("key", "")
                    if not obj_key or obj_key in active_db_keys or obj_key in used_storage_keys:
                        continue

                    # Check object age
                    lm = obj.get("last_modified")
                    is_old = False
                    if isinstance(lm, datetime):
                        is_old = (lm < cutoff_dt) if lm.tzinfo else (lm.replace(tzinfo=timezone.utc) < cutoff_dt)
                    elif isinstance(lm, (int, float)):
                        is_old = lm < cutoff_timestamp

                    if is_old:
                        orphan_keys.append(obj_key)
                        report.bytes_reclaimed += obj.get("size", 0)

                report.orphan_r2_objects_deleted = len(orphan_keys)
                keys_to_delete.extend(orphan_keys)
            except Exception as e:
                logger.warning("Error scanning orphan storage objects in R2: %s", e)
                report.errors.append(f"Orphan scan warning: {e}")

            # Deduplicate keys to delete
            unique_keys_to_delete = list(dict.fromkeys(keys_to_delete))
            report.deleted_storage_keys = unique_keys_to_delete

            # 4. Perform actual deletion if not a dry run
            if not dry_run:
                # Delete objects from Cloudflare R2 / Storage
                if unique_keys_to_delete:
                    deleted_count = storage_service.delete_objects(unique_keys_to_delete)
                    logger.info(
                        "DataCleaner deleted %s objects from storage (retention: %s days)",
                        deleted_count,
                        days,
                    )

                # Delete corresponding unused artifact rows from DB
                if artifacts_to_delete:
                    artifact_ids_to_del = [a.id for a in artifacts_to_delete]
                    chunk_size = 500
                    for i in range(0, len(artifact_ids_to_del), chunk_size):
                        chunk = artifact_ids_to_del[i : i + chunk_size]
                        db.execute(delete(Artifact).where(Artifact.id.in_(chunk)))
                    db.commit()
                    report.database_records_pruned = len(artifact_ids_to_del)

            report.duration_seconds = time.perf_counter() - start_time
            res_dict = report.to_dict()
            cls._last_report = res_dict

            logger.info(
                "DataCleaner policy executed (%s): deleted %s unused images, %s orphan R2 objects, "
                "preserved %s active images, reclaimed %s bytes in %.2fs",
                "DRY_RUN" if dry_run else "LIVE",
                report.unused_images_deleted,
                report.orphan_r2_objects_deleted,
                report.used_images_preserved,
                report.bytes_reclaimed,
                report.duration_seconds,
            )
            return res_dict

        except Exception as exc:
            db.rollback()
            report.errors.append(str(exc))
            report.duration_seconds = time.perf_counter() - start_time
            logger.error("DataCleaner policy execution failed: %s", exc, exc_info=True)
            res_dict = report.to_dict()
            cls._last_report = res_dict
            return res_dict

    @classmethod
    def apply_r2_bucket_lifecycle_configuration(cls) -> dict[str, Any]:
        """Apply native S3/Cloudflare R2 bucket lifecycle rule for temporary scratch/staging prefixes.

        Sets a 3-day automatic expiration rule on temporary upload prefixes in the bucket.
        """
        if not storage_service.use_r2 or not storage_service.s3_client:
            return {"status": "skipped", "reason": "Cloudflare R2 not configured"}

        try:
            lifecycle_policy = {
                "Rules": [
                    {
                        "ID": "deckpilot-scratch-3day-cleanup",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "scratch/"},
                        "Expiration": {"Days": 3},
                    },
                    {
                        "ID": "deckpilot-temp-3day-cleanup",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "tmp/"},
                        "Expiration": {"Days": 3},
                    },
                    {
                        "ID": "deckpilot-staging-3day-cleanup",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "staging/"},
                        "Expiration": {"Days": 3},
                    },
                ]
            }
            storage_service.s3_client.put_bucket_lifecycle_configuration(
                Bucket=storage_service.bucket,
                LifecycleConfiguration=lifecycle_policy,
            )
            logger.info("Successfully configured Cloudflare R2 bucket lifecycle rules (3-day expiration)")
            return {"status": "success", "rules_applied": 3, "bucket": storage_service.bucket}
        except Exception as e:
            logger.warning("Could not set Cloudflare R2 bucket lifecycle configuration: %s", e)
            return {"status": "warning", "error": str(e)}
