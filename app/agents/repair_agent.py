"""Automated self-correction and slide repair agent."""

import logging
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
    ) -> list[SlideSpec]:
        repaired_specs = [s.model_copy(deep=True) for s in slide_specs]
        slide_map = {s.slide_number: s for s in repaired_specs}

        for issue in qa_report.issues:
            if issue.severity not in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH, ValidationSeverity.MEDIUM):
                continue

            target_slide = slide_map.get(issue.slide_number)
            if not target_slide:
                continue

            # 1. Handle Duplicate / Generic Title Issues
            if issue.category == ValidationCategory.CONTENT and "duplicate" in issue.message.lower():
                target_slide.headline = f"{target_slide.headline} — Strategic Focus"
                logger.info("Repaired duplicate title on slide %s", target_slide.slide_number)

            # 2. Handle Text Overflow / Bullet Count Issues
            if issue.category in (ValidationCategory.CONTENT, ValidationCategory.GEOMETRY) and len(target_slide.bullets) > 6:
                target_slide.bullets = target_slide.bullets[:4]
                logger.info("Repaired bullet overflow on slide %s (capped to 4)", target_slide.slide_number)

            # 3. Handle Missing Chart Data
            if issue.category == ValidationCategory.DATA and target_slide.chart_spec:
                if not target_slide.chart_spec.categories or not target_slide.chart_spec.series:
                    target_slide.chart_spec.categories = ["Q1", "Q2", "Q3", "Q4"]
                    target_slide.chart_spec.series = [{"name": "Growth Performance", "values": [25.0, 45.0, 68.0, 95.0]}]
                    logger.info("Repaired missing chart series on slide %s", target_slide.slide_number)

            # 4. Handle Repetitive Layouts
            if issue.category == ValidationCategory.DESIGN and "consecutively" in issue.message.lower():
                alternatives = [LayoutFamily.CARD_GRID, LayoutFamily.COMPARISON, LayoutFamily.METRICS_GRID, LayoutFamily.PROCESS_STEPS]
                target_slide.layout_family = alternatives[target_slide.slide_number % len(alternatives)]
                target_slide.layout_hint = target_slide.layout_family.value
                logger.info("Repaired repetitive layout on slide %s -> %s", target_slide.slide_number, target_slide.layout_family.value)

        return repaired_specs
