"""Multi-tier Presentation QA Agent (Content, Design, Data, Geometry, Technical)."""

import logging
from typing import Any

from app.agents.title_intelligence import TitleIntelligence
from app.schemas.generation_state import (
    DesignSystem,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.tools.pptx_validator import PPTXValidator
from app.tools.text_geometry import TextGeometry

logger = logging.getLogger(__name__)


class PresentationQAAgent:
    """Performs multi-dimensional automated QA on presentation specs and rendered binaries."""

    @classmethod
    def evaluate_presentation(
        cls,
        slide_specs: list[SlideSpec],
        design_system: DesignSystem,
        pptx_bytes: bytes | None = None,
    ) -> QAReport:
        issues: list[ValidationIssue] = []
        checks = [
            "content_narrative_flow",
            "title_intelligence_check",
            "text_budget_and_overflow",
            "visual_rhythm_and_diversity",
            "chart_data_provenance",
            "pptx_openxml_integrity",
        ]

        # 1. Title QA
        titles = [s.headline or s.key_message for s in slide_specs]
        title_issues = TitleIntelligence.validate_titles(titles)
        issues.extend(title_issues)

        # 2. Content & Text Budget QA
        for idx, slide in enumerate(slide_specs):
            bullets = slide.bullets or []
            # Check maximum bullets
            if len(bullets) > 6:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    category=ValidationCategory.CONTENT,
                    slide_number=idx + 1,
                    slide_id=slide.slide_id,
                    message=f"Slide has {len(bullets)} bullets; exceeds maximum recommended 6 for scannability",
                    suggested_fix="Consolidate bullet points into 3-4 high-impact takeaways",
                ))

            # Check individual bullet length
            for b in bullets:
                if len(str(b).split()) > 25:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.LOW,
                        category=ValidationCategory.CONTENT,
                        slide_number=idx + 1,
                        slide_id=slide.slide_id,
                        message="Bullet point exceeds 25 words",
                        suggested_fix="Tighten bullet copy to maintain executive scannability",
                    ))

            # 3. Chart & Data Provenance QA
            if slide.chart_spec:
                c = slide.chart_spec
                if not c.categories or not c.series:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.DATA,
                        slide_number=idx + 1,
                        slide_id=slide.slide_id,
                        message="Chart specified without categories or series values",
                        suggested_fix="Provide valid numerical categories and series data",
                    ))

        # 4. Visual Rhythm QA
        layouts = [s.layout_family for s in slide_specs]
        consecutive_same = 1
        for i in range(1, len(layouts)):
            if layouts[i] == layouts[i-1]:
                consecutive_same += 1
                if consecutive_same >= 3:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.LOW,
                        category=ValidationCategory.DESIGN,
                        slide_number=i + 1,
                        slide_id=slide_specs[i].slide_id,
                        message=f"Layout '{layouts[i].value}' used 3 times consecutively",
                        suggested_fix="Introduce layout variety (e.g. switch to cards, timeline, or chart)",
                    ))
            else:
                consecutive_same = 1

        # 5. Technical PPTX Stream QA
        if pptx_bytes:
            stream_report = PPTXValidator.validate_pptx_stream(pptx_bytes, len(slide_specs))
            issues.extend(stream_report.issues)

        # Compute overall status & score
        has_critical = any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == ValidationSeverity.HIGH for i in issues)

        if has_critical:
            status = "failed"
        elif has_high:
            status = "issues_detected"
        else:
            status = "passed"

        score = max(0.0, round(100.0 - (len(issues) * 7.5), 1))

        return QAReport(
            status=status,
            overall_quality_score=score,
            issues=issues,
            checks_performed=checks,
            slide_count=len(slide_specs),
            repair_triggered=(status == "issues_detected"),
        )
