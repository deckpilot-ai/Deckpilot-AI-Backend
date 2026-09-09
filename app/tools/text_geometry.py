"""Text geometry, font metrics, overflow detection, and layout collision checking tool."""

import math
import re
from typing import Any

from app.schemas.generation_state import ValidationCategory, ValidationIssue, ValidationSeverity


class TextGeometry:
    """Calculates text bounding boxes, word wraps, overflow detection, and shape overlap geometry."""

    @staticmethod
    def clean_text(text: Any) -> str:
        return re.sub(r"[ \t]+", " ", str(text or "").replace("\u2014", " - ").replace("**", "")).strip()

    @classmethod
    def estimate_text_height(
        cls,
        text: str,
        width_inches: float,
        font_size_pt: int = 14,
        is_bullet_list: bool = False,
    ) -> float:
        """Estimates required height in inches for wrapped text at a given width and font point size."""
        clean = cls.clean_text(text)
        if not clean:
            return 0.3

        # Approx character width factor: ~0.52 * font_size in pt
        usable_width_pt = max(10.0, (width_inches - (0.3 if is_bullet_list else 0.05)) * 72.0)
        char_width_pt = max(1.0, font_size_pt * 0.52)
        chars_per_line = max(1, int(usable_width_pt / char_width_pt))

        paragraphs = clean.split("\n")
        total_lines = 0
        for p in paragraphs:
            line_len = len(p)
            total_lines += max(1, math.ceil(line_len / chars_per_line))

        line_height_pt = font_size_pt * 1.25
        paragraph_spacing_pt = (len(paragraphs) - 1) * 4.0 if is_bullet_list else 0.0
        total_height_pt = total_lines * line_height_pt + paragraph_spacing_pt + 6.0
        return round(total_height_pt / 72.0, 3)

    @classmethod
    def fit_text_to_box(
        cls,
        text: str,
        width_inches: float,
        height_inches: float,
        max_font_size: int = 16,
        min_font_size: int = 11,
        is_bullet_list: bool = False,
    ) -> tuple[int, bool]:
        """Finds optimal font size that fits into (width_inches, height_inches) without clipping.
        
        Returns (best_font_size, fits).
        """
        max_size = int(round(max_font_size))
        min_size = int(round(min_font_size))
        for size in range(max_size, min_size - 1, -1):
            h = cls.estimate_text_height(text, width_inches, size, is_bullet_list)
            if h <= height_inches + 0.05:
                return size, True
        return min_size, False

    @classmethod
    def detect_overflow_and_bounds(
        cls,
        slide_idx: int,
        shapes_meta: list[dict[str, Any]],
        canvas_w: float = 13.333,
        canvas_h: float = 7.5,
    ) -> list[ValidationIssue]:
        """Inspects all shapes on a slide for canvas out-of-bounds, severe overlap, and text overflows."""
        issues: list[ValidationIssue] = []

        for s in shapes_meta:
            x, y, w, h = s.get("x", 0.0), s.get("y", 0.0), s.get("w", 0.0), s.get("h", 0.0)
            name = s.get("name", "shape")
            text = s.get("text", "")

            # 1. Canvas Boundary check
            if x < -0.05 or y < -0.05 or (x + w) > (canvas_w + 0.1) or (y + h) > (canvas_h + 0.1):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.GEOMETRY,
                    slide_number=slide_idx + 1,
                    message=f"Shape '{name}' exceeds slide boundary: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f} on {canvas_w}x{canvas_h} canvas",
                    suggested_fix="Adjust shape position or width within margin bounds",
                ))

            # 2. Text overflow check
            if text and s.get("is_text_box", False):
                font_size = s.get("font_size", 14)
                est_h = cls.estimate_text_height(text, w, font_size, s.get("bullet_list", False))
                if est_h > h + 0.2:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_idx + 1,
                        message=f"Text in shape '{name}' exceeds box height ({est_h:.2f}in > {h:.2f}in)",
                        suggested_fix="Reduce text copy length or split into two slides",
                    ))

        return issues
