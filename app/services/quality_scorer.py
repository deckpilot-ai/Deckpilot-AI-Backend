"""Weighted PresentationQualityScore engine adhering to the 14 Quality Gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.generation_state import (
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)


@dataclass
class QualityGateResult:
    gate_id: str
    name: str
    weight: float
    score: float
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class PresentationScoreCard:
    overall_quality_score: float
    is_presentation_ready: bool
    status: str  # "PASSED", "REPAIRED_AND_PASSED", "FAILED"
    gate_results: dict[str, QualityGateResult]
    slide_scores: dict[int, float]
    critical_issues_count: int
    high_issues_count: int
    medium_issues_count: int
    low_issues_count: int
    summary_findings: list[str]


class PresentationQualityScorer:
    """Calculates granular and weighted 14-Gate presentation quality metrics."""

    GATE_WEIGHTS: dict[str, float] = {
        "QG1_pptx_validity": 0.05,
        "QG2_text_safety": 0.20,
        "QG3_typography": 0.08,
        "QG4_geometry": 0.12,
        "QG5_collision": 0.15,
        "QG6_icons": 0.05,
        "QG7_images": 0.08,
        "QG8_source_utilization": 0.08,
        "QG9_slide_density": 0.05,
        "QG10_layout_semantics": 0.05,
        "QG11_visual_balance": 0.05,
        "QG12_theme_consistency": 0.04,
        "QG13_content_quality": 0.08,
        "QG14_editability": 0.02,
    }

    @classmethod
    def calculate_slide_score(cls, slide_number: int, slide_issues: list[ValidationIssue]) -> float:
        """Calculates 0-100 quality score for an individual slide."""
        deductions = 0.0
        for issue in slide_issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                deductions += 35.0
            elif issue.severity == ValidationSeverity.HIGH:
                deductions += 15.0
            elif issue.severity == ValidationSeverity.MEDIUM:
                deductions += 6.0
            elif issue.severity == ValidationSeverity.LOW:
                deductions += 2.0
        return max(0.0, round(100.0 - deductions, 1))

    @classmethod
    def score_presentation(
        cls,
        slides: list[SlideSpec],
        qa_report: QAReport,
        repair_iterations: int = 0,
    ) -> PresentationScoreCard:
        """Computes comprehensive score card across all 14 Quality Gates."""
        issues = qa_report.issues
        crit = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        high = [i for i in issues if i.severity == ValidationSeverity.HIGH]
        med = [i for i in issues if i.severity == ValidationSeverity.MEDIUM]
        low = [i for i in issues if i.severity == ValidationSeverity.LOW]

        # Calculate per-slide scores
        slide_scores: dict[int, float] = {}
        for idx in range(1, len(slides) + 1):
            s_issues = [i for i in issues if i.slide_number == idx]
            slide_scores[idx] = cls.calculate_slide_score(idx, s_issues)

        # Map issues to the 14 Quality Gates
        gate_issues: dict[str, list[ValidationIssue]] = {k: [] for k in cls.GATE_WEIGHTS}

        for issue in issues:
            cid = issue.checkpoint_id or ""
            cat_name = str(issue.category.value if hasattr(issue.category, "value") else (issue.category or "")).upper()
            msg = issue.message.lower()

            if "corrupt" in msg or "reopen" in msg or cid in ("QA-109", "QA-110"):
                gate_issues["QG1_pptx_validity"].append(issue)
            elif "overflow" in msg or "clip" in msg or cid in ("QA-038", "QA-039"):
                gate_issues["QG2_text_safety"].append(issue)
            elif cat_name == "TYPOGRAPHY" or cid in ("QA-025", "QA-026", "QA-027", "QA-028", "QA-029", "QA-030", "QA-031", "QA-032"):
                gate_issues["QG3_typography"].append(issue)
            elif "align" in msg or "gutter" in msg or cid in ("QA-044", "QA-045", "QA-046", "QA-047"):
                gate_issues["QG4_geometry"].append(issue)
            elif "collide" in msg or "overlap" in msg or cid in ("QA-040", "QA-041", "QA-042", "QA-043"):
                gate_issues["QG5_collision"].append(issue)
            elif "icon" in msg or cid in ("QA-083", "QA-086"):
                gate_issues["QG6_icons"].append(issue)
            elif cat_name == "IMAGES" or "image" in msg or cid in ("QA-061", "QA-062", "QA-063", "QA-064", "QA-066", "QA-067", "QA-068", "QA-069", "QA-070", "QA-071", "QA-072"):
                gate_issues["QG7_images"].append(issue)
            elif "grounding" in msg or cid in ("QA-065", "QA-101"):
                gate_issues["QG8_source_utilization"].append(issue)
            elif "underfilled" in msg or "crowded" in msg or "sparse" in msg or cid in ("QA-049", "QA-059", "QA-060"):
                gate_issues["QG9_slide_density"].append(issue)
            elif "layout" in msg or cid in ("QA-075", "QA-076", "QA-077", "QA-078", "QA-079", "QA-080", "QA-081", "QA-122", "QA-123"):
                gate_issues["QG10_layout_semantics"].append(issue)
            elif "balance" in msg or "blank" in msg or cid in ("QA-050", "QA-051", "QA-052", "QA-053", "QA-054", "QA-055"):
                gate_issues["QG11_visual_balance"].append(issue)
            elif cat_name == "DESIGN" or cid in ("QA-085", "QA-088", "QA-089", "QA-090", "QA-091", "QA-092"):
                gate_issues["QG12_theme_consistency"].append(issue)
            elif cat_name == "CONTENT" or cid in ("QA-001", "QA-002", "QA-003", "QA-004", "QA-005", "QA-009", "QA-010", "QA-013", "QA-014", "QA-015", "QA-121"):
                gate_issues["QG13_content_quality"].append(issue)
            else:
                gate_issues["QG14_editability"].append(issue)

        gate_results: dict[str, QualityGateResult] = {}
        weighted_sum = 0.0

        for gate_id, weight in cls.GATE_WEIGHTS.items():
            g_issues = gate_issues[gate_id]
            gate_deductions = sum(
                (30.0 if i.severity == ValidationSeverity.CRITICAL else (14.0 if i.severity == ValidationSeverity.HIGH else 5.0))
                for i in g_issues
            )
            g_score = max(0.0, round(100.0 - gate_deductions, 1))
            g_passed = not any(i.severity == ValidationSeverity.CRITICAL for i in g_issues) and g_score >= 80.0
            gate_results[gate_id] = QualityGateResult(
                gate_id=gate_id,
                name=gate_id.replace("_", " ").title(),
                weight=weight,
                score=g_score,
                passed=g_passed,
                issues=g_issues,
            )
            weighted_sum += (g_score * weight)

        overall_score = round(weighted_sum, 1)

        # Hard Gate Enforcement: A deck cannot pass if it contains ANY critical defects
        has_critical = len(crit) > 0
        is_ready = (not has_critical) and (len(high) <= 1) and (overall_score >= 88.0)

        if is_ready:
            status = "REPAIRED_AND_PASSED" if repair_iterations > 0 else "PASSED"
        else:
            status = "FAILED"

        summary = [f"[Slide {i.slide_number}] {i.message}" for i in (crit + high)[:6]]

        return PresentationScoreCard(
            overall_quality_score=overall_score,
            is_presentation_ready=is_ready,
            status=status,
            gate_results=gate_results,
            slide_scores=slide_scores,
            critical_issues_count=len(crit),
            high_issues_count=len(high),
            medium_issues_count=len(med),
            low_issues_count=len(low),
            summary_findings=summary,
        )
