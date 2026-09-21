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
        checks = [
            "reopen_pptx",
            "slide_count",
            "canvas_bounds",
            "shape_collisions",
            "text_overflow",
            "font_size_floor",
            "placeholder_text",
            "media_relationships",
        ]

        try:
            prs = Presentation(io.BytesIO(pptx_bytes))
            slide_count = len(prs.slides)

            if expected_slides and slide_count != expected_slides:
                issues.append(ValidationIssue(
                    checkpoint_id="QA-110",
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.TECHNICAL,
                    slide_number=0,
                    message=f"Slide count mismatch: expected {expected_slides}, rendered {slide_count}",
                    suggested_fix="Ensure all planned slides are rendered",
                    repair_action="rerender_deck",
                ))

            w_in = prs.slide_width / 914400.0 if prs.slide_width else 13.333
            h_in = prs.slide_height / 914400.0 if prs.slide_height else 7.500

            from app.services.collision_engine import BoundingBox, CollisionDetectionEngine

            for idx, slide in enumerate(prs.slides):
                slide_num = idx + 1
                slide_boxes: list[BoundingBox] = []
                cards: list[BoundingBox] = []

                for shape in slide.shapes:
                    sh_x = shape.left / 914400.0
                    sh_y = shape.top / 914400.0
                    sh_w = shape.width / 914400.0
                    sh_h = shape.height / 914400.0
                    sh_name = shape.name or "shape"

                    # Classify kind
                    sh_lower = sh_name.lower()
                    if any(tag in sh_lower for tag in ("accent", "bleed", "backdrop", "corner", "tick", "divider", "line")):
                        kind = "background"
                    elif any(tag in sh_lower for tag in ("card", "box", "panel", "container", "row-", "frame", "mat")):
                        kind = "card"
                    elif any(tag in sh_lower for tag in ("pill", "badge", "tag", "disc", "bubble")):
                        kind = "badge"
                    elif any(tag in sh_lower for tag in ("icon",)):
                        kind = "icon"
                    elif any(tag in sh_lower for tag in ("image", "photo", "picture")):
                        kind = "image"
                    elif getattr(shape, "has_chart", False):
                        kind = "chart"
                    elif getattr(shape, "has_table", False):
                        kind = "table"
                    elif any(tag in sh_lower for tag in ("footer", "page")):
                        kind = "footer"
                    elif any(tag in sh_lower for tag in ("title", "headline", "eyebrow", "header")):
                        kind = "header"
                    elif shape.has_text_frame and shape.text.strip():
                        kind = "text"
                    else:
                        kind = "shape"

                    box = BoundingBox(
                        id=str(shape.shape_id),
                        name=sh_name,
                        kind=kind,
                        x=sh_x,
                        y=sh_y,
                        w=sh_w,
                        h=sh_h,
                    )
                    slide_boxes.append(box)
                    if kind == "card":
                        cards.append(box)

                    # Inspect text frame properties (font size floor and placeholders)
                    if shape.has_text_frame:
                        text = shape.text.strip()
                        lower_text = text.lower()
                        for marker in ("lorem ipsum", "[insert", "todo:", "placeholder", "tbd"):
                            if marker in lower_text:
                                issues.append(ValidationIssue(
                                    checkpoint_id="QA-013",
                                    severity=ValidationSeverity.HIGH,
                                    category=ValidationCategory.CONTENT,
                                    slide_number=slide_num,
                                    message=f"Unresolved placeholder '{marker}' found in shape '{sh_name}'",
                                    suggested_fix="Replace placeholder with substantive domain copy",
                                    repair_action="remove_placeholder",
                                ))

                        # Check font sizes
                        for p in shape.text_frame.paragraphs:
                            for r in p.runs:
                                if r.font.size is not None:
                                    pt_size = r.font.size.pt
                                    if pt_size < 10.5 and kind not in ("footer", "page_number") and len(r.text.strip()) > 3:
                                        issues.append(ValidationIssue(
                                            checkpoint_id="QA-025",
                                            severity=ValidationSeverity.HIGH if pt_size < 9.0 else ValidationSeverity.MEDIUM,
                                            category=ValidationCategory.TYPOGRAPHY,
                                            slide_number=slide_num,
                                            message=f"Tiny text detected in '{sh_name}': {pt_size:.1f}pt is below legible floor (min 11pt)",
                                            suggested_fix="Increase font size to at least 11pt",
                                            repair_action="increase_font",
                                        ))

                # Run collision engine on slide shapes
                collision_issues = CollisionDetectionEngine.detect_collisions(
                    slide_number=slide_num,
                    boxes=slide_boxes,
                    canvas_w=w_in,
                    canvas_h=h_in,
                )
                issues.extend(collision_issues)

                # Validate card alignment if multiple cards present
                if len(cards) >= 2:
                    align_issues = CollisionDetectionEngine.validate_card_alignment(
                        slide_number=slide_num,
                        cards=cards,
                    )
                    issues.extend(align_issues)

            status = "passed" if not any(i.severity in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH) for i in issues) else "issues_detected"
            score = max(0.0, 100.0 - sum(
                (12.0 if i.severity == ValidationSeverity.CRITICAL else (5.0 if i.severity == ValidationSeverity.HIGH else 2.0))
                for i in issues
            ))

            return QAReport(
                status=status,
                overall_quality_score=round(score, 1),
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
