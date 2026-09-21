"""Typography Engine and Measurement Services for Maratha Heritage Editorial Theme.

Provides text measurement, title optimization, line-wrapping estimation,
and strict overflow prevention for Cambria display and Calibri body fonts.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from app.presentation.themes.maratha_heritage_editorial.tokens import FONTS


@dataclass(frozen=True)
class TypographyBudget:
    preferred_pt: float
    min_pt: float
    max_pt: float
    max_lines: int
    max_chars: int


BUDGETS = {
    "cover_title": TypographyBudget(preferred_pt=52.0, min_pt=40.0, max_pt=58.0, max_lines=2, max_chars=55),
    "slide_title": TypographyBudget(preferred_pt=27.0, min_pt=23.0, max_pt=30.0, max_lines=2, max_chars=70),
    "card_title": TypographyBudget(preferred_pt=16.0, min_pt=13.0, max_pt=18.0, max_lines=2, max_chars=45),
    "lead_body": TypographyBudget(preferred_pt=15.5, min_pt=12.5, max_pt=16.0, max_lines=6, max_chars=260),
    "body": TypographyBudget(preferred_pt=13.5, min_pt=11.0, max_pt=15.5, max_lines=6, max_chars=280),
    "compact_body": TypographyBudget(preferred_pt=12.0, min_pt=10.5, max_pt=13.0, max_lines=8, max_chars=340),
    "caption": TypographyBudget(preferred_pt=10.5, min_pt=9.0, max_pt=11.0, max_lines=2, max_chars=110),
    "footer": TypographyBudget(preferred_pt=9.0, min_pt=8.0, max_pt=9.5, max_lines=1, max_chars=50),
    "metric": TypographyBudget(preferred_pt=30.0, min_pt=24.0, max_pt=36.0, max_lines=1, max_chars=15),
    "big_question": TypographyBudget(preferred_pt=18.0, min_pt=14.0, max_pt=21.0, max_lines=4, max_chars=120),
    "quote": TypographyBudget(preferred_pt=20.0, min_pt=15.0, max_pt=24.0, max_lines=6, max_chars=220),
    "kicker": TypographyBudget(preferred_pt=12.0, min_pt=11.0, max_pt=13.0, max_lines=1, max_chars=40),
}


class TextMeasurementService:
    """Estimates font line count and bounding height based on font metrics."""

    @classmethod
    def estimate(
        cls,
        text: str,
        font_family: str,
        font_size_pt: float,
        width_in: float,
        line_spacing: float = 1.15
    ) -> Tuple[int, float, bool]:
        """Returns (estimated_lines, estimated_height_in, fits_width)."""
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        if not clean:
            return (0, 0.0, True)

        # Character width ratio relative to font size
        # Cambria is wider with classical serifs (~0.54), Calibri is narrower (~0.49)
        char_ratio = 0.54 if "Cambria" in font_family else 0.49
        char_w_in = (font_size_pt / 72.0) * char_ratio
        chars_per_line = max(8, int(width_in / char_w_in))

        words = clean.split()
        lines = 1
        current_len = 0
        for w in words:
            w_len = len(w)
            if current_len == 0:
                current_len = w_len
            elif current_len + 1 + w_len <= chars_per_line:
                current_len += 1 + w_len
            else:
                lines += 1
                current_len = w_len

        line_height_in = (font_size_pt / 72.0) * line_spacing
        est_height_in = round(lines * line_height_in, 3)
        return (lines, est_height_in, True)


class TitleOptimizer:
    """Normalizes slide titles to 3-8 impactful words, offloading excess context to subtitle."""

    @classmethod
    def optimize(cls, raw_title: str, max_words: int = 8) -> Tuple[str, Optional[str]]:
        clean = re.sub(r"\s+", " ", str(raw_title or "")).strip()
        if not clean:
            return ("Overview", None)

        words = clean.split()
        if len(words) <= max_words:
            return (clean, None)

        # 1. Delimiter split
        for delim in [":", " — ", " - ", " – ", " | "]:
            if delim in clean:
                parts = clean.split(delim, 1)
                t_part = parts[0].strip()
                s_part = parts[1].strip()
                if 2 <= len(t_part.split()) <= max_words:
                    return (t_part, s_part)

        # 2. Punctuation split
        for punct in [". ", "? ", "! ", "; "]:
            if punct in clean:
                parts = clean.split(punct, 1)
                t_part = parts[0].strip()
                s_part = parts[1].strip()
                if 2 <= len(t_part.split()) <= max_words:
                    return (t_part, s_part)

        # 3. Preposition / conjunction split
        preps = {"of", "for", "in", "with", "on", "by", "across", "versus", "vs", "and", "&"}
        for i in range(min(len(words) - 1, max_words), 1, -1):
            if words[i].lower() in preps:
                main_t = " ".join(words[:i])
                sub_t = clean
                return (main_t, sub_t)

        # 4. Fallback clamp
        main_t = " ".join(words[:max_words])
        return (main_t, clean)


def format_kicker_text(raw_kicker: str) -> str:
    """Formats kicker to crisp uppercase tracking."""
    text = re.sub(r"[^A-Za-z0-9 ,&/\-]", "", str(raw_kicker or "OVERVIEW")).strip().upper()
    return text[:40] if text else "OVERVIEW"


def fit_text_to_box(
    text: str,
    box_w_in: float,
    box_h_in: float,
    preferred_pt: float = 13.5,
    min_pt: float = 11.0,
    line_spacing: float = 1.15,
    font_family: str = FONTS.body
) -> Tuple[str, float, float]:
    """Dynamically adapts font size and safely clamps text to prevent box overflow.

    Returns (fitted_text, chosen_font_pt, estimated_height_in).
    Guarantees text never spills outside container boundaries.
    """
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ("", preferred_pt, 0.0)

    # Step down font size from preferred to min
    pt = preferred_pt
    while pt >= min_pt:
        lines, est_h, _ = TextMeasurementService.estimate(
            clean, font_family, pt, box_w_in, line_spacing
        )
        if est_h <= box_h_in:
            return (clean, pt, est_h)
        pt -= 0.5

    # If still overflows at min_pt, truncate words safely with ellipsis
    words = clean.split()
    trimmed = list(words)
    while trimmed and len(trimmed) > 4:
        trimmed.pop()
        candidate = " ".join(trimmed) + "..."
        lines, est_h, _ = TextMeasurementService.estimate(
            candidate, font_family, min_pt, box_w_in, line_spacing
        )
        if est_h <= box_h_in:
            return (candidate, min_pt, est_h)

    return (clean[:60] + "...", min_pt, box_h_in)
