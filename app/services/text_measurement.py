"""High-precision text measurement, font metrics, and overflow detection service."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from app.schemas.generation_state import (
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)

# Character width ratios relative to font size (in points)
# e.g., for Segoe UI at 14pt, average char width is 14 * 0.49 = 6.86 pt
FONT_CHAR_WIDTH_RATIOS: dict[str, float] = {
    "segoe ui": 0.495,
    "calibri": 0.465,
    "cambria": 0.485,
    "arial": 0.515,
    "helvetica": 0.510,
    "trebuchet ms": 0.525,
    "georgia": 0.540,
    "times new roman": 0.450,
    "verdana": 0.580,
    "roboto": 0.490,
    "montserrat": 0.535,
    "outfit": 0.520,
    "playfair display": 0.510,
    "cinzel": 0.530,
    "cormorant": 0.460,
    "cormorant garamond": 0.460,
    "inter": 0.505,
    "lora": 0.495,
    "merriweather": 0.530,
    "poppins": 0.535,
    "lato": 0.485,
    "raleway": 0.510,
    "open sans": 0.515,
    "default": 0.500,
}

# Line height factors relative to font size
FONT_LINE_HEIGHT_RATIOS: dict[str, float] = {
    "title": 1.18,
    "headline": 1.22,
    "subheading": 1.25,
    "body": 1.30,
    "bullet": 1.32,
    "caption": 1.20,
}


@dataclass(frozen=True)
class TextMeasurementResult:
    estimated_width_in: float
    estimated_height_in: float
    line_count: int
    lines: list[str]
    fits: bool
    overflow_height_in: float
    recommended_font_size_pt: float


class TextMeasurementService:
    """Calculates high-precision typography layout bounds, word-wrap splits, and container fit."""

    @staticmethod
    def clean(text: Any) -> str:
        val = str(text or "").replace("\u2014", " - ").replace("\u2013", " - ")
        val = re.sub(r"[\t ]+", " ", val)
        return val.strip()

    @classmethod
    def get_char_width_pt(cls, font_name: str, font_size_pt: float) -> float:
        font_key = font_name.strip().lower() if font_name else "default"
        ratio = FONT_CHAR_WIDTH_RATIOS.get(font_key, FONT_CHAR_WIDTH_RATIOS["default"])
        return max(1.0, font_size_pt * ratio)

    @classmethod
    def wrap_text(
        cls,
        text: str,
        font_name: str,
        font_size_pt: float,
        max_width_in: float,
        is_bullet_list: bool = False,
        padding_in: float = 0.04,
    ) -> list[str]:
        """Wraps text into lines based on exact character metrics."""
        cleaned = cls.clean(text)
        if not cleaned:
            return []

        usable_width_pt = max(20.0, (max_width_in - padding_in - (0.25 if is_bullet_list else 0.0)) * 72.0)
        char_w = cls.get_char_width_pt(font_name, font_size_pt)
        max_chars_per_line = max(1, int(usable_width_pt / char_w))

        paragraphs = cleaned.split("\n")
        all_lines: list[str] = []

        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue

            words = para_clean.split()
            current_line: list[str] = []
            current_len = 0

            for word in words:
                word_len = len(word)
                if not current_line:
                    current_line.append(word)
                    current_len = word_len
                elif current_len + 1 + word_len <= max_chars_per_line:
                    current_line.append(word)
                    current_len += 1 + word_len
                else:
                    all_lines.append(" ".join(current_line))
                    current_line = [word]
                    current_len = word_len

            if current_line:
                all_lines.append(" ".join(current_line))

        return all_lines

    @classmethod
    def measure_text_bounds(
        cls,
        text: str,
        font_name: str = "Segoe UI",
        font_size_pt: float = 14.0,
        max_width_in: float = 6.0,
        role: str = "body",
        is_bullet_list: bool = False,
        padding_in: float = 0.04,
    ) -> tuple[float, float, int, list[str]]:
        """Measures bounding box (width_in, height_in, line_count, lines) for text wrapped within max_width_in."""
        lines = cls.wrap_text(text, font_name, font_size_pt, max_width_in, is_bullet_list, padding_in)
        if not lines:
            return 0.0, 0.0, 0, []

        char_w = cls.get_char_width_pt(font_name, font_size_pt)
        max_line_len = max(len(l) for l in lines)
        est_width_in = min(max_width_in, round((max_line_len * char_w) / 72.0 + padding_in, 3))

        line_ratio = FONT_LINE_HEIGHT_RATIOS.get(role, 1.30)
        line_height_pt = font_size_pt * line_ratio
        para_gap_pt = 4.0 if is_bullet_list else 2.0
        total_height_pt = len(lines) * line_height_pt + (len(text.split("\n")) - 1) * para_gap_pt + 4.0
        est_height_in = round(total_height_pt / 72.0, 3)

        return est_width_in, est_height_in, len(lines), lines

    @classmethod
    def fit_text_into_container(
        cls,
        text: str,
        container_w: float,
        container_h: float,
        font_name: str = "Segoe UI",
        min_font_pt: float = 11.0,
        max_font_pt: float = 18.0,
        role: str = "body",
        is_bullet_list: bool = False,
        padding_in: float = 0.08,
    ) -> TextMeasurementResult:
        """Determines if text fits within container and computes optimal font size or overflow delta."""
        cleaned = cls.clean(text)
        if not cleaned:
            return TextMeasurementResult(
                estimated_width_in=0.0,
                estimated_height_in=0.0,
                line_count=0,
                lines=[],
                fits=True,
                overflow_height_in=0.0,
                recommended_font_size_pt=max_font_pt,
            )

        # Step down from max_font_pt to min_font_pt by 0.5 increments
        curr = max_font_pt
        best_lines: list[str] = []
        best_w = 0.0
        best_h = 0.0

        while curr >= min_font_pt:
            w, h, _, lines = cls.measure_text_bounds(
                cleaned, font_name, curr, container_w, role, is_bullet_list, padding_in
            )
            if h <= container_h + 0.02 and w <= container_w + 0.02:
                return TextMeasurementResult(
                    estimated_width_in=w,
                    estimated_height_in=h,
                    line_count=len(lines),
                    lines=lines,
                    fits=True,
                    overflow_height_in=0.0,
                    recommended_font_size_pt=curr,
                )
            best_lines = lines
            best_w = w
            best_h = h
            curr -= 0.5

        # If it doesn't fit even at min_font_pt, calculate overflow
        overflow = round(best_h - container_h, 3)
        return TextMeasurementResult(
            estimated_width_in=best_w,
            estimated_height_in=best_h,
            line_count=len(best_lines),
            lines=best_lines,
            fits=False,
            overflow_height_in=max(0.01, overflow),
            recommended_font_size_pt=min_font_pt,
        )

    @classmethod
    def validate_slide_text_elements(
        cls,
        slide_number: int,
        elements: list[dict[str, Any]],
        font_name: str = "Segoe UI",
    ) -> list[ValidationIssue]:
        """Validates all text containers on a slide for overflow, clipping, or sub-floor font sizing."""
        issues: list[ValidationIssue] = []

        for elem in elements:
            text = elem.get("text", "")
            if not text:
                continue

            name = elem.get("name", "text_element")
            w = float(elem.get("w", 1.0))
            h = float(elem.get("h", 1.0))
            min_font = float(elem.get("min_font_pt", 11.0))
            max_font = float(elem.get("max_font_pt", 14.0))
            is_title = bool(elem.get("is_title", False))
            is_bullet = bool(elem.get("is_bullet", False))
            role = "title" if is_title else ("bullet" if is_bullet else "body")

            result = cls.fit_text_into_container(
                text=text,
                container_w=w,
                container_h=h,
                font_name=font_name,
                min_font_pt=min_font,
                max_font_pt=max_font,
                role=role,
                is_bullet_list=is_bullet,
            )

            if not result.fits:
                sev = ValidationSeverity.CRITICAL if result.overflow_height_in > 0.4 else ValidationSeverity.HIGH
                issues.append(
                    ValidationIssue(
                        checkpoint_id="QA-038",
                        severity=sev,
                        category=ValidationCategory.GEOMETRY,
                        slide_number=slide_number,
                        message=(
                            f"Text in '{name}' overflows container by {result.overflow_height_in:.2f}\" "
                            f"at minimum font size {min_font:.0f}pt (text length: {len(text)} chars, {result.line_count} lines)"
                        ),
                        suggested_fix="Summarize card body text or expand card container height",
                        auto_fixable=True,
                        repair_action="shorten_and_reflow",
                    )
                )

        return issues

    @classmethod
    def check_fits(
        cls,
        text: str,
        w: float,
        h: float,
        size: float = 13.0,
        font_name: str = "Segoe UI",
        bullet_list: bool = False,
        role: str = "body",
        padding_in: float = 0.04,
    ) -> bool:
        """Determines if text wrapped into width `w` at font size `size` fits inside height `h`."""
        cleaned = cls.clean(text)
        if not cleaned:
            return True
        _, est_h, _, _ = cls.measure_text_bounds(
            cleaned,
            font_name=font_name,
            font_size_pt=size,
            max_width_in=w,
            role=role,
            is_bullet_list=bullet_list,
            padding_in=padding_in,
        )
        return est_h <= (h + 0.02)

    @classmethod
    def calculate_text_height(
        cls,
        text: str,
        width_in: float,
        font_name: str = "Segoe UI",
        font_size_pt: float = 14.0,
        role: str = "body",
        bullet_list: bool = False,
        padding_in: float = 0.04,
    ) -> float:
        """Calculates precise vertical height of wrapped text in inches."""
        cleaned = cls.clean(text)
        if not cleaned:
            return 0.0
        _, est_h, _, _ = cls.measure_text_bounds(
            cleaned,
            font_name=font_name,
            font_size_pt=font_size_pt,
            max_width_in=width_in,
            role=role,
            is_bullet_list=bullet_list,
            padding_in=padding_in,
        )
        return est_h

    @classmethod
    def measure_title_fits(
        cls,
        text: str,
        max_width_in: float,
        max_height_in: float = 1.2,
        font_name: str = "Segoe UI",
        min_font_pt: float = 20.0,
        max_font_pt: float = 32.0,
    ) -> tuple[bool, float, list[str]]:
        """Finds optimal title font size that fits container without wrapping onto >2 lines or overflowing height."""
        cleaned = cls.clean(text)
        if not cleaned:
            return True, max_font_pt, []

        curr = max_font_pt
        best_lines: list[str] = []
        while curr >= min_font_pt:
            _, est_h, lines_cnt, lines = cls.measure_text_bounds(
                cleaned, font_name=font_name, font_size_pt=curr, max_width_in=max_width_in, role="title"
            )
            # Presentation titles shouldn't exceed 2 lines and must fit in height
            if est_h <= (max_height_in + 0.02) and lines_cnt <= 2:
                return True, curr, lines
            best_lines = lines
            curr -= 1.0

        return False, min_font_pt, best_lines

    @classmethod
    def split_content_for_layout(
        cls,
        bullets: list[str],
        container_w: float,
        container_h: float,
        font_name: str = "Segoe UI",
        font_size_pt: float = 13.0,
    ) -> tuple[bool, list[str], list[str]]:
        """Splits bullets into those that fit in the container and those that overflow.
        
        Returns (all_fit, fitting_bullets, overflow_bullets).
        """
        valid_bullets = [cls.clean(b) for b in bullets if cls.clean(b)]
        if not valid_bullets:
            return True, [], []

        fitting: list[str] = []
        overflow: list[str] = []

        for b in valid_bullets:
            test_list = fitting + [b]
            combined = "\n".join(test_list)
            if cls.check_fits(combined, container_w, container_h, size=font_size_pt, font_name=font_name, bullet_list=True):
                fitting.append(b)
            else:
                overflow.append(b)

        return (len(overflow) == 0), fitting, overflow
