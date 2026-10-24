"""Typography Engine and Measurement Services for Federalism Editorial Theme.

Provides text measurement, title optimization, line-wrapping estimation,
and strict overflow prevention for Cambria display and Calibri body fonts.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from app.presentation.themes.federalism_editorial.tokens import FONTS


@dataclass(frozen=True)
class TypographyBudget:
    preferred_pt: float
    min_pt: float
    max_pt: float
    max_lines: int
    max_chars: int


BUDGETS = {
    "cover_title": TypographyBudget(preferred_pt=56.0, min_pt=42.0, max_pt=62.0, max_lines=2, max_chars=60),
    "slide_title": TypographyBudget(preferred_pt=32.0, min_pt=26.0, max_pt=36.0, max_lines=2, max_chars=75),
    "dark_section_title": TypographyBudget(preferred_pt=38.0, min_pt=30.0, max_pt=42.0, max_lines=2, max_chars=65),
    "card_title": TypographyBudget(preferred_pt=15.5, min_pt=13.5, max_pt=17.5, max_lines=2, max_chars=48),
    "lead_body": TypographyBudget(preferred_pt=15.0, min_pt=13.0, max_pt=16.5, max_lines=4, max_chars=180),
    "standard_body": TypographyBudget(preferred_pt=12.0, min_pt=10.5, max_pt=13.5, max_lines=6, max_chars=240),
    "kicker": TypographyBudget(preferred_pt=12.5, min_pt=11.0, max_pt=13.5, max_lines=1, max_chars=35),
    "caption": TypographyBudget(preferred_pt=10.5, min_pt=9.0, max_pt=11.5, max_lines=2, max_chars=100),
    "footer": TypographyBudget(preferred_pt=9.5, min_pt=8.5, max_pt=10.0, max_lines=1, max_chars=40),
    "metric": TypographyBudget(preferred_pt=34.0, min_pt=26.0, max_pt=44.0, max_lines=1, max_chars=12),
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
        # Cambria is wider and has taller serifs (~0.54), Calibri is narrower (~0.48)
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
    return text[:35] if text else "OVERVIEW"


def fit_text_to_box(
    text: str,
    box_w_in: float,
    box_h_in: float,
    preferred_pt: float = 12.0,
    min_pt: float = 10.5,
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

    current_pt = preferred_pt
    while current_pt >= min_pt - 0.01:
        lines, est_h, _ = TextMeasurementService.estimate(
            clean, font_family, current_pt, box_w_in, line_spacing=line_spacing
        )
        if est_h <= box_h_in + 0.05:
            return (clean, round(current_pt, 1), est_h)
        current_pt -= 0.5

    # If still doesn't fit at min_pt, gracefully trim words with ellipsis
    current_pt = min_pt
    words = clean.split()
    while len(words) > 4:
        words.pop()
        candidate = " ".join(words) + "…"
        lines, est_h, _ = TextMeasurementService.estimate(
            candidate, font_family, current_pt, box_w_in, line_spacing=line_spacing
        )
        if est_h <= box_h_in + 0.05:
            return (candidate, current_pt, est_h)

    return (clean[:40] + "…", min_pt, box_h_in)
