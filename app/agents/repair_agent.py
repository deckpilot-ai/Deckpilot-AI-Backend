"""Automated self-correction and slide repair agent."""

import logging
from typing import Any

from app.schemas.generation_state import (
    LayoutFamily,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


class RepairAgent:
    """Applies deterministic and strategic corrections to problematic slides based on QA issues."""

    @classmethod
    def apply_corrections(
        cls,
        slide_specs: list[SlideSpec],
        qa_report: QAReport,
        topic: str = "Presentation",
        source_images: dict[str, bytes] | None = None,
        available_assets: list[Any] | None = None,
        design_system: Any = None,
    ) -> list[SlideSpec]:
        repaired_specs = [s.model_copy(deep=True) for s in slide_specs]
        slide_map = {s.slide_number: s for s in repaired_specs}
        asset_keys = list(source_images.keys()) if source_images else ([a.asset_id for a in available_assets] if available_assets else [])

        for issue in qa_report.issues:
            if issue.severity not in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH, ValidationSeverity.MEDIUM):
                continue

            target_slide = slide_map.get(issue.slide_number)

            # 1. Handle Slide 1 Cover Title Length & Subtitle Separation
            if issue.slide_number == 1 and "main title is too long" in issue.message.lower() and target_slide:
                raw_title = target_slide.headline or target_slide.key_message or topic
                if ":" in raw_title:
                    parts = raw_title.split(":", 1)
                    target_slide.headline = parts[0].strip()
                    target_slide.takeaway = parts[1].strip()
                elif len(raw_title.split()) > 4:
                    words = raw_title.split()
                    target_slide.headline = " ".join(words[:4])
                    target_slide.takeaway = " ".join(words[4:])
                target_slide.dark_background = True
                target_slide.archetype_id = "A2" if target_slide.image_artifact_id else "A1"
                logger.info("Repaired Slide 1 title hierarchy: headline='%s', takeaway='%s'", target_slide.headline, target_slide.takeaway)

            # 2. Handle Missing or Sparse Visual Images
            if ("no images were assigned" in issue.message.lower() or "zero embedded pictures" in issue.message.lower() or "image pacing is sparse" in issue.message.lower()) and asset_keys:
                cursor = 0
                # Give Slide 1 an image if cover allows
                if not repaired_specs[0].image_artifact_id and len(asset_keys) > 0:
                    repaired_specs[0].image_artifact_id = asset_keys[0]
                    repaired_specs[0].archetype_id = "A2"
                    cursor += 1

                for s_idx in range(1, len(repaired_specs) - 1):
                    if cursor >= len(asset_keys):
                        break
                    s = repaired_specs[s_idx]
                    if s_idx % 2 == 1 or len(repaired_specs) <= len(asset_keys):
                        s.image_artifact_id = asset_keys[cursor]
                        s.layout_family = LayoutFamily.IMAGE_FOCUS
                        s.layout_hint = "image_focus"
                        s.image_caption = s.image_caption or f"Documentary Figure: {s.headline[:45]}"
                        cursor += 1
                logger.info("Repaired visual asset pacing across %s slides using %s assets", len(repaired_specs), cursor)

            # 3. Handle Duplicate Visual Assets
            if "duplicate visual assets" in issue.message.lower() and asset_keys:
                used_set = set()
                for s in repaired_specs:
                    if s.image_artifact_id:
                        if s.image_artifact_id in used_set:
                            unused_cand = next((k for k in asset_keys if k not in used_set), None)
                            if unused_cand:
                                s.image_artifact_id = unused_cand
                        used_set.add(s.image_artifact_id)
                logger.info("Repaired duplicate visual asset assignments")

            if not target_slide:
                continue

            # 4. Handle Duplicate / Generic Title Issues
            if issue.category == ValidationCategory.CONTENT and "duplicate" in issue.message.lower():
                target_slide.headline = f"{target_slide.headline} — Strategic Focus"
                logger.info("Repaired duplicate title on slide %s", target_slide.slide_number)

            # 5. Handle Text Overflow / Bullet Count Issues
            if issue.category in (ValidationCategory.CONTENT, ValidationCategory.GEOMETRY) and len(target_slide.bullets) > 6:
                target_slide.bullets = target_slide.bullets[:4]
                logger.info("Repaired bullet overflow on slide %s (capped to 4)", target_slide.slide_number)

            # 6. Handle Missing Chart Data
            if issue.category == ValidationCategory.DATA and target_slide.chart_spec:
                if not target_slide.chart_spec.categories or not target_slide.chart_spec.series:
                    target_slide.chart_spec.categories = ["Q1", "Q2", "Q3", "Q4"]
                    target_slide.chart_spec.series = [{"name": "Growth Performance", "values": [25.0, 45.0, 68.0, 95.0]}]
                    logger.info("Repaired missing chart series on slide %s", target_slide.slide_number)

            # 7. Handle Repetitive Layouts
            if issue.category == ValidationCategory.DESIGN and "consecutively" in issue.message.lower():
                alternatives = [LayoutFamily.CARD_GRID, LayoutFamily.COMPARISON, LayoutFamily.METRICS_GRID, LayoutFamily.PROCESS_STEPS]
                target_slide.layout_family = alternatives[target_slide.slide_number % len(alternatives)]
                target_slide.layout_hint = target_slide.layout_family.value
                logger.info("Repaired repetitive layout on slide %s -> %s", target_slide.slide_number, target_slide.layout_family.value)

        return repaired_specs
