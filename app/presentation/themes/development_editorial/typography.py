"""Typography system, title normalization, and text budget control for the Development Editorial Theme."""

import re
from dataclasses import dataclass
from typing import Tuple
from app.presentation.themes.development_editorial.tokens import FONTS, COLORS


@dataclass
class TextBudget:
    max_chars: int
    preferred_font_size: float
    min_font_size: float
    max_lines: int


BUDGETS = {
    "slide_title": TextBudget(max_chars=90, preferred_font_size=33.0, min_font_size=26.0, max_lines=2),
    "cover_title": TextBudget(max_chars=60, preferred_font_size=48.0, min_font_size=36.0, max_lines=2),
    "kicker": TextBudget(max_chars=40, preferred_font_size=13.0, min_font_size=12.0, max_lines=1),
    "body_lead": TextBudget(max_chars=280, preferred_font_size=16.0, min_font_size=14.0, max_lines=4),
    "card_title": TextBudget(max_chars=50, preferred_font_size=16.5, min_font_size=14.5, max_lines=2),
    "card_body": TextBudget(max_chars=160, preferred_font_size=13.0, min_font_size=11.5, max_lines=4),
    "quote_text": TextBudget(max_chars=180, preferred_font_size=20.0, min_font_size=16.0, max_lines=4),
    "metric_value": TextBudget(max_chars=15, preferred_font_size=34.0, min_font_size=28.0, max_lines=1),
}


TITLE_META_PREFIXES = [
    r'^(an?\s+)?(inquiry|study|analysis|examination|overview|investigation|introduction)\s+(in|to|into|of|on)\s+',
    r'^(understanding|exploring|examining|investigating|analyzing|discovering|learning|looking\s+at)\s+',
    r'^(a\s+closer\s+look\s+at|insights\s+on|thoughts\s+on)\s+',
]


def normalize_title(raw_title: str, max_words: int = 4) -> Tuple[str, str]:
    """Normalizes a slide title to a punchy, impactful editorial headline.
    
    Guarantees that the main title is between 1 and 4 words maximum.
    Any secondary context is moved to the subtitle/lead prose to preserve
    full comprehension while maximizing visual authority.
    """
    clean = re.sub(r"\s+", " ", str(raw_title or "")).strip()
    if not clean:
        return ("Overview", "")

    # 1. Check natural separators (colon, em-dash, en-dash, hyphen)
    sub_extra = ""
    for sep in (":", " — ", " – ", " - "):
        if sep in clean:
            parts = clean.split(sep, 1)
            left = parts[0].strip()
            right = parts[1].strip()
            left_words = left.split()
            if 1 <= len(left_words) <= max_words:
                return (left, right)
            clean = left
            sub_extra = right
            break

    # 2. Strip fluff meta prefixes ("Understanding", "Exploring", "An analysis of", etc.)
    stripped = clean
    for pat in TITLE_META_PREFIXES:
        m = re.match(pat, stripped, re.IGNORECASE)
        if m:
            stripped = stripped[m.end():].strip()
            break

    words = stripped.split()
    if 1 <= len(words) <= max_words:
        sub = sub_extra or (clean if stripped.lower() != clean.lower() else "")
        return (stripped, sub)

    # 4. If title has leading articles ('The', 'A', 'An'), check if dropping it brings to <= max_words
    if words[0].lower() in {"the", "a", "an"}:
        no_article = words[1:]
        if 1 <= len(no_article) <= max_words:
            return (" ".join(no_article), clean)

    # 5. Extract impactful phrase before prepositions/conjunctions
    preps = {"of", "for", "in", "with", "on", "by", "across", "versus", "vs", "and", "&"}
    for i in range(min(len(words) - 1, max_words), 1, -1):
        if words[i].lower() in preps:
            main_t = " ".join(words[:i])
            sub_t = clean
            return (main_t, sub_t)

    # 6. Fallback: clamp cleanly to first max_words words
    main_t = " ".join(words[:max_words])
    sub_t = clean
    return (main_t, sub_t)


def format_kicker_text(raw_kicker: str) -> str:
    """Formats kicker to crisp uppercase tracking."""
    text = re.sub(r"[^A-Za-z0-9 ,&/\-]", "", str(raw_kicker or "OVERVIEW")).strip().upper()
    return text[:35] if text else "OVERVIEW"


def fit_font_size(text: str, budget_key: str) -> float:
    """Calculates ideal font size adhering to strict budget floors (no unreadable shrinking)."""
    budget = BUDGETS.get(budget_key)
    if not budget:
        return 13.0
    
    length = len(str(text or ""))
    if length <= budget.max_chars * 0.7:
        return budget.preferred_font_size
    
    # Scale smoothly between preferred and min
    excess_ratio = min(1.0, (length - budget.max_chars * 0.7) / (budget.max_chars * 0.3 + 1e-5))
    size = budget.preferred_font_size - excess_ratio * (budget.preferred_font_size - budget.min_font_size)
    return round(max(budget.min_font_size, size), 1)


def fit_text_to_box(
    text: str,
    box_w_in: float,
    box_h_in: float,
    preferred_pt: float = 12.5,
    min_pt: float = 10.5,
    line_spacing: float = 1.15,
    font_char_ratio: float = 0.52
) -> Tuple[str, float, float]:
    """Dynamically adapts font size and safely clamps text to prevent box overflow.
    
    Returns (fitted_text, chosen_font_pt, estimated_height_in).
    Guarantees text never spills outside box boundaries.
    """
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ("", preferred_pt, 0.0)

    words = clean.split()
    current_pt = preferred_pt

    # Step down font size from preferred to min_pt in 0.5pt decrements
    while current_pt >= min_pt - 0.01:
        char_w = (current_pt / 72.0) * font_char_ratio
        chars_per_line = max(8, int(box_w_in / char_w))
        line_h = (current_pt * line_spacing) / 72.0
        max_lines = max(1, int(box_h_in / line_h))

        lines = []
        cur_line = []
        cur_len = 0
        for w in words:
            w_len = len(w)
            if cur_len + (1 if cur_len > 0 else 0) + w_len <= chars_per_line:
                cur_line.append(w)
                cur_len += (1 if cur_len > 0 else 0) + w_len
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = w_len
        if cur_line:
            lines.append(" ".join(cur_line))

        needed_h = len(lines) * line_h
        if needed_h <= box_h_in + 0.02:
            return (clean, round(current_pt, 1), round(needed_h, 2))

        current_pt -= 0.5

    # If still overflowing at min_pt, truncate cleanly at word boundary
    char_w = (min_pt / 72.0) * font_char_ratio
    chars_per_line = max(8, int(box_w_in / char_w))
    line_h = (min_pt * line_spacing) / 72.0
    max_lines = max(1, int(box_h_in / line_h))

    lines = []
    cur_line = []
    cur_len = 0
    for w in words:
        w_len = len(w)
        if cur_len + (1 if cur_len > 0 else 0) + w_len <= chars_per_line:
            cur_line.append(w)
            cur_len += (1 if cur_len > 0 else 0) + w_len
        else:
            if cur_line:
                lines.append(" ".join(cur_line))
                if len(lines) >= max_lines:
                    break
            cur_line = [w]
            cur_len = w_len
    if len(lines) < max_lines and cur_line:
        lines.append(" ".join(cur_line))

    # Append ellipsis if text was truncated
    if len(lines) >= max_lines:
        last = lines[-1]
        words_last = last.split()
        if len(words_last) > 1:
            lines[-1] = " ".join(words_last[:-1]) + "..."
        else:
            lines[-1] = last[:max(4, len(last) - 4)] + "..."

    final_text = " ".join(lines)
    final_h = min(box_h_in, len(lines) * line_h)
    return (final_text, min_pt, round(final_h, 2))

