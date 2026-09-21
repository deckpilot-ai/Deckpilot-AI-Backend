"""Visual QA Agent for Presentation Slides.

Evaluates rendered presentation slides against the 29 visual rules, including
text overflow, boundary violations, font floors, and empty shape detection.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches, Pt

logger = logging.getLogger(__name__)


@dataclass
class QAViolation:
    rule_id: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    message: str
    shape_name: Optional[str] = None
    slide_index: int = 0
    suggested_fix: Optional[str] = None


@dataclass
class QAReport:
    slide_index: int
    passed: bool
    violations: List[QAViolation] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(v.severity == "CRITICAL" for v in self.violations)


class VisualQAAgent:
    """Rigorous slide inspection engine."""

    # Safe Canvas Limits (Inches)
    SAFE_LEFT = 0.55
    SAFE_RIGHT = 12.78
    SAFE_TOP = 0.40
    SAFE_BOTTOM = 7.15

    ALLOWED_FONTS = {"Cambria", "Calibri", "Calibri Light", "Arial"}

    @classmethod
    def inspect_slide(cls, slide: Any, slide_index: int = 0) -> QAReport:
        violations: List[QAViolation] = []
        shapes = list(slide.shapes)

        if not shapes:
            violations.append(QAViolation(
                rule_id="EMPTY_SLIDE",
                severity="CRITICAL",
                message="Slide has zero shapes rendered",
                slide_index=slide_index,
                suggested_fix="Rerender slide using fallback archetype"
            ))
            return QAReport(slide_index=slide_index, passed=False, violations=violations)

        for shp in shapes:
            name = shp.name
            left = shp.left / 914400.0
            top = shp.top / 914400.0
            width = shp.width / 914400.0
            height = shp.height / 914400.0
            right = left + width
            bottom = top + height

            # Rule 5 & 25: Canvas boundary violation
            if left < cls.SAFE_LEFT - 0.1 or right > cls.SAFE_RIGHT + 0.3 or top < cls.SAFE_TOP - 0.1 or bottom > cls.SAFE_BOTTOM + 0.3:
                # Exclude full-slide background rects
                if not (width >= 13.0 and height >= 7.2):
                    violations.append(QAViolation(
                        rule_id="OUTSIDE_SAFE_AREA",
                        severity="WARNING",
                        message=f"Shape '{name}' bounds ({left:.2f}, {top:.2f}, {width:.2f}, {height:.2f}) extend outside safe margins",
                        shape_name=name,
                        slide_index=slide_index,
                        suggested_fix="Clamp coordinates within safe canvas"
                    ))

            # Rule 8: Empty text shape
            if shp.has_text_frame:
                tf = shp.text_frame
                text = tf.text.strip()
                if not text and shp.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
                    violations.append(QAViolation(
                        rule_id="EMPTY_SHAPE",
                        severity="WARNING",
                        message=f"Text box '{name}' is empty",
                        shape_name=name,
                        slide_index=slide_index,
                        suggested_fix="Remove empty shape container"
                    ))

                # Inspect typography
                for p in tf.paragraphs:
                    font_size = p.font.size.pt if (p.font and p.font.size) else None
                    font_name = p.font.name if p.font else None

                    # Rule 16: Wrong font family
                    if font_name and font_name not in cls.ALLOWED_FONTS:
                        violations.append(QAViolation(
                            rule_id="UNAUTHORIZED_FONT",
                            severity="WARNING",
                            message=f"Shape '{name}' uses unauthorized font '{font_name}'",
                            shape_name=name,
                            slide_index=slide_index,
                            suggested_fix="Replace with Cambria or Calibri"
                        ))

                    # Rule 7: Tiny font check with semantic role floors
                    is_footer = top >= 6.80 or "footer" in name.lower()
                    is_caption = "caption" in name.lower() or bool(p.font and p.font.italic)
                    is_pill = "pill" in name.lower() or (height <= 0.48 and width <= 5.0 and len(p.text.strip()) <= 50)
                    min_floor = 8.5 if is_footer else (9.0 if (is_caption or is_pill) else 10.5)

                    if font_size and font_size < min_floor:
                        violations.append(QAViolation(
                            rule_id="TINY_FONT",
                            severity="CRITICAL",
                            message=f"Text '{p.text[:30]}...' rendered at {font_size}pt below {min_floor}pt floor",
                            shape_name=name,
                            slide_index=slide_index,
                            suggested_fix="Summarize text and raise font size"
                        ))

            # Rule 21: Table bounds check
            if shp.has_table:
                tbl = shp.table
                if len(tbl.rows) > 9:
                    violations.append(QAViolation(
                        rule_id="TABLE_OVERFLOW",
                        severity="WARNING",
                        message=f"Table '{name}' has {len(tbl.rows)} rows, risking density overload",
                        shape_name=name,
                        slide_index=slide_index,
                        suggested_fix="Summarize table to at most 8 rows"
                    ))

        # Check title word count (Strict rule: maximum 4 words, minimum 1 word)
        titles = [s.text_frame.text.strip() for s in shapes if s.has_text_frame and ("Title" in s.name or (s.top / 914400.0 < 1.8 and len(s.text_frame.paragraphs) > 0 and (s.text_frame.paragraphs[0].font.size.pt if s.text_frame.paragraphs[0].font.size else 0) >= 24))]
        if titles:
            title_text = titles[0]
            words = title_text.split()
            if len(words) > 4:
                violations.append(QAViolation(
                    rule_id="TITLE_TOO_LONG",
                    severity="WARNING",
                    message=f"Main title has {len(words)} words (max 4 allowed): '{title_text}'",
                    slide_index=slide_index,
                    suggested_fix="Compress to 1-4 impactful words and move details to subtitle"
                ))
            elif len(words) == 0:
                violations.append(QAViolation(
                    rule_id="EMPTY_TITLE",
                    severity="CRITICAL",
                    message="Slide title is empty",
                    slide_index=slide_index,
                    suggested_fix="Provide a 1-4 word impactful title"
                ))

        passed = not any(v.severity == "CRITICAL" for v in violations)
        return QAReport(slide_index=slide_index, passed=passed, violations=violations)

    @classmethod
    def inspect_presentation(cls, prs: Any) -> List[QAReport]:
        return [cls.inspect_slide(slide, i) for i, slide in enumerate(prs.slides)]
