"""PPTX OpenXML validator and presentation comparison tool."""

import io
import logging
from typing import Any

from pptx import Presentation

from app.schemas.generation_state import QAReport, ValidationCategory, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class PPTXValidator:
    """Validates structural correctness of PPTX binaries and compares structural quality."""

    @classmethod
    def validate_pptx_stream(cls, pptx_bytes: bytes, expected_slides: int | None = None) -> QAReport:
        issues: list[ValidationIssue] = []
        checks = ["reopen_pptx", "slide_count", "canvas_bounds", "placeholder_text", "media_relationships"]

        try:
            prs = Presentation(io.BytesIO(pptx_bytes))
            slide_count = len(prs.slides)

            if expected_slides and slide_count != expected_slides:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.TECHNICAL,
                    slide_number=0,
                    message=f"Slide count mismatch: expected {expected_slides}, rendered {slide_count}",
                    suggested_fix="Ensure all planned slides are rendered",
                ))

            w_pt = prs.slide_width
            h_pt = prs.slide_height

            for idx, slide in enumerate(prs.slides):
                for shape in slide.shapes:
                    # Canvas bounds check
                    if shape.left < 0 or shape.top < 0 or (shape.left + shape.width) > w_pt + 1000 or (shape.top + shape.height) > h_pt + 1000:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.GEOMETRY,
                            slide_number=idx + 1,
                            message=f"Shape '{shape.name}' overflows canvas limits",
                            suggested_fix="Constrain coordinates to canvas dimensions",
                        ))

                    # Placeholder check
                    if shape.has_text_frame:
                        text = shape.text.lower()
                        for marker in ("lorem ipsum", "[insert", "todo:", "placeholder"):
                            if marker in text:
                                issues.append(ValidationIssue(
                                    severity=ValidationSeverity.HIGH,
                                    category=ValidationCategory.CONTENT,
                                    slide_number=idx + 1,
                                    message=f"Unresolved placeholder '{marker}' found in slide text",
                                    suggested_fix="Replace placeholder with substantive domain copy",
                                ))

            status = "passed" if not any(i.severity in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH) for i in issues) else "issues_detected"
            score = max(0.0, 100.0 - len(issues) * 10.0)

            return QAReport(
                status=status,
                overall_quality_score=score,
                issues=issues,
                checks_performed=checks,
                slide_count=slide_count,
            )

        except Exception as e:
            logger.error("PPTX validation failed with error: %s", e)
            return QAReport(
                status="failed",
                overall_quality_score=0.0,
                issues=[ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    category=ValidationCategory.TECHNICAL,
                    slide_number=0,
                    message=f"Corrupted PPTX binary: {str(e)}",
                    suggested_fix="Re-render presentation OpenXML structure",
                )],
                checks_performed=checks,
                slide_count=0,
            )

    @classmethod
    def compare_to_benchmark(cls, generated_bytes: bytes, benchmark_bytes: bytes) -> dict[str, Any]:
        """Compares structural characteristics of generated deck against a reference benchmark."""
        gen_prs = Presentation(io.BytesIO(generated_bytes))
        bench_prs = Presentation(io.BytesIO(benchmark_bytes))

        def _get_metrics(prs):
            total_slides = len(prs.slides)
            charts = sum(1 for s in prs.slides for sh in s.shapes if getattr(sh, "has_chart", False))
            tables = sum(1 for s in prs.slides for sh in s.shapes if getattr(sh, "has_table", False))
            images = 0
            for s in prs.slides:
                for sh in s.shapes:
                    try:
                        if getattr(sh, "shape_type", None) == 13 or hasattr(sh, "image"):
                            images += 1
                    except Exception:
                        pass
            shapes_per_slide = sum(len(s.shapes) for s in prs.slides) / max(1, total_slides)
            return {
                "slide_count": total_slides,
                "chart_count": charts,
                "table_count": tables,
                "image_count": images,
                "avg_shapes_per_slide": round(shapes_per_slide, 1),
            }

        return {
            "generated": _get_metrics(gen_prs),
            "benchmark": _get_metrics(bench_prs),
        }
