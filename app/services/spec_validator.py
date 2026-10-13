"""Layer-1 Deck Specification Validator and Sanitizer.

Ported and enhanced from deckpilot-skill/scripts/validate_spec.py.
Validates word budgets, layout variety, chart data integrity, placeholder text,
and structural constraints BEFORE rendering, and provides auto-sanitization.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MAX_TITLE_WORDS = 10
MAX_TITLE_CHARS = 72
MAX_BULLET_WORDS = 15
MAX_CARD_HEADING_WORDS = 5
MAX_CARD_BODY_WORDS = 20
MAX_STAT_LABEL_WORDS = 5
MAX_TABLE_ROWS = 6
MAX_TABLE_COLS = 5
MAX_CELL_WORDS = 6
MAX_SAME_LAYOUT = 3

PLACEHOLDER_REGEX = re.compile(r"lorem|ipsum|\bTODO\b|\[insert|\bTBD\b|xxxx|\bplaceholder\b", re.IGNORECASE)
FORMAT_ARTIFACT_REGEX = re.compile(r"(^|\")\s*[\u2022\*\-]\s|\*\*")


def word_count(text: Any) -> int:
    return len(re.findall(r"\S+", str(text or "")))


def issue(slide: int, code: str, msg: str, severity: str = "error", path: str = "") -> dict[str, Any]:
    return {"slide": slide, "code": code, "severity": severity, "message": msg, "path": path}


class SpecValidator:
    """Validates and auto-sanitizes deck specifications before PowerPoint rendering."""

    @classmethod
    def validate_spec(cls, spec: dict[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        slides = spec.get("slides", [])
        if not isinstance(slides, list) or not slides:
            issues.append(issue(0, "NO_SLIDES", "Presentation spec contains no slides"))
            return issues

        deck_title = spec.get("deckTitle") or spec.get("title") or ""
        if deck_title and word_count(deck_title) > 12:
            issues.append(issue(0, "TITLE_LONG", f"Deck title has {word_count(deck_title)} words (max 12)", "warning", "deckTitle"))

        layouts_used: list[str] = []

        for idx, slide in enumerate(slides, 1):
            if not isinstance(slide, dict):
                continue

            layout = str(slide.get("layoutHint") or slide.get("layout") or slide.get("archetype_id") or "")
            layouts_used.append(layout)

            # 1. Headline / Title check
            title = slide.get("headline") or slide.get("title") or slide.get("message") or ""
            if title:
                wc = word_count(title)
                if wc > MAX_TITLE_WORDS and layout not in ("title_dark", "hero", "closing"):
                    issues.append(issue(idx, "TITLE_LONG", f"Title has {wc} words (max {MAX_TITLE_WORDS}): '{title}'", "error", "title"))
                if len(title) > MAX_TITLE_CHARS and layout not in ("title_dark", "hero", "closing"):
                    issues.append(issue(idx, "TITLE_CHARS_LONG", f"Title has {len(title)} characters (max {MAX_TITLE_CHARS})", "warning", "title"))
                if title.rstrip().endswith("."):
                    issues.append(issue(idx, "TITLE_PERIOD", "Headline should not end with a period", "warning", "title"))

            # 2. Bullets word count & items count
            bullets = slide.get("bullets") or slide.get("key_points") or []
            if isinstance(bullets, list):
                if len(bullets) > 6 and layout not in ("council_eight", "A25", "A19"):
                    issues.append(issue(idx, "TOO_MANY_ITEMS", f"Slide has {len(bullets)} bullets (recommended max 5)", "warning", "bullets"))
                for b_i, b in enumerate(bullets):
                    b_str = b if isinstance(b, str) else json.dumps(b)
                    b_wc = word_count(b_str)
                    if b_wc > MAX_BULLET_WORDS:
                        issues.append(issue(idx, "WORD_LIMIT", f"Bullet {b_i+1} has {b_wc} words (max {MAX_BULLET_WORDS})", "error", f"bullets[{b_i}]"))

            # 3. Cards / Columns check
            cards = slide.get("cards") or slide.get("items") or []
            if isinstance(cards, list):
                for c_i, card in enumerate(cards):
                    if isinstance(card, dict):
                        h_wc = word_count(card.get("heading") or card.get("title") or "")
                        if h_wc > MAX_CARD_HEADING_WORDS:
                            issues.append(issue(idx, "HEADING_LONG", f"Card {c_i+1} heading has {h_wc} words (max {MAX_CARD_HEADING_WORDS})", "error", f"cards[{c_i}].heading"))
                        b_wc = word_count(card.get("body") or card.get("desc") or "")
                        if b_wc > MAX_CARD_BODY_WORDS:
                            issues.append(issue(idx, "BODY_LONG", f"Card {c_i+1} body has {b_wc} words (max {MAX_CARD_BODY_WORDS})", "error", f"cards[{c_i}].body"))

            # 4. Table check
            table = slide.get("table")
            if isinstance(table, dict):
                headers = table.get("headers") or table.get("header") or []
                rows = table.get("rows") or []
                if len(headers) > MAX_TABLE_COLS or len(rows) > MAX_TABLE_ROWS:
                    issues.append(issue(idx, "TABLE_TOO_BIG", f"Table has {len(rows)} rows x {len(headers)} columns (max {MAX_TABLE_ROWS}x{MAX_TABLE_COLS})", "warning", "table"))

            # 5. Chart data integrity
            chart = slide.get("chart")
            if isinstance(chart, dict):
                labels = chart.get("labels") or chart.get("categories") or []
                series = chart.get("series") or []
                for s_i, se in enumerate(series):
                    vals = se.get("values") or []
                    if len(vals) != len(labels):
                        issues.append(issue(idx, "CHART_MISMATCH", f"Chart series {s_i+1} has {len(vals)} values but {len(labels)} labels", "error", "chart.series"))

            # 6. Placeholder / formatting check
            blob = json.dumps(slide, ensure_ascii=False)
            if PLACEHOLDER_REGEX.search(blob):
                issues.append(issue(idx, "PLACEHOLDER_TEXT", "Unresolved placeholder copy detected in slide spec", "error", "content"))
            if FORMAT_ARTIFACT_REGEX.search(blob):
                issues.append(issue(idx, "FORMAT_CHARS", "Raw markdown syntax or literal bullet characters detected in slide spec", "warning", "formatting"))

        # Deck-level layout variety checks
        for i in range(1, len(layouts_used)):
            if layouts_used[i] and layouts_used[i] == layouts_used[i - 1] and layouts_used[i] not in ("section_divider", "divider"):
                issues.append(issue(i + 1, "DUPLICATE_LAYOUT", f"Layout '{layouts_used[i]}' repeats consecutive slide {i}", "warning", "layout"))

        for l_name in set(layouts_used):
            if l_name and layouts_used.count(l_name) > MAX_SAME_LAYOUT and l_name not in ("title_dark", "closing", "section_divider", "hero"):
                issues.append(issue(0, "LAYOUT_OVERUSE", f"Layout '{l_name}' used {layouts_used.count(l_name)} times (max {MAX_SAME_LAYOUT})", "warning", "layout"))

        return issues

    @classmethod
    def sanitize_spec_inplace(cls, spec: dict[str, Any]) -> dict[str, Any]:
        """Automatically sanitizes and repairs spec defects before rendering."""
        slides = spec.get("slides", [])
        if not isinstance(slides, list):
            return spec

        deck_title = spec.get("deckTitle") or spec.get("title") or ""
        if isinstance(deck_title, str) and deck_title:
            cleaned_dt = deck_title.strip().rstrip(".")
            dt_words = cleaned_dt.split()
            if len(dt_words) > MAX_TITLE_WORDS:
                cleaned_dt = " ".join(dt_words[:MAX_TITLE_WORDS])
            if "deckTitle" in spec:
                spec["deckTitle"] = cleaned_dt
            if "title" in spec:
                spec["title"] = cleaned_dt

        recent_layouts: list[str] = []

        for idx, slide in enumerate(slides, 1):
            if not isinstance(slide, dict):
                continue

            # 1. Sanitize Headline: strip period, trim to max 10 words if excessive
            title = slide.get("headline") or slide.get("title") or slide.get("message") or ""
            if isinstance(title, str) and title:
                cleaned_title = title.strip().rstrip(".")
                words = cleaned_title.split()
                if len(words) > MAX_TITLE_WORDS:
                    # Keep first 10 impactful words
                    cleaned_title = " ".join(words[:MAX_TITLE_WORDS])
                slide["headline"] = cleaned_title
                slide["title"] = cleaned_title
                slide["message"] = cleaned_title

            # 2. Sanitize Bullets: strip literal bullet chars, bold asterisks, enforce max 15 words
            bullets = slide.get("bullets") or slide.get("key_points") or []
            if isinstance(bullets, list):
                sanitized_bullets = []
                for b in bullets:
                    if isinstance(b, str):
                        clean_b = re.sub(r"^[\s\u2022\*\-]+", "", b).replace("**", "").strip()
                        # Clean placeholder text
                        if PLACEHOLDER_REGEX.search(clean_b):
                            clean_b = f"Documented operational benchmark for {title or deck_title}"
                        w_list = clean_b.split()
                        if len(w_list) > MAX_BULLET_WORDS:
                            clean_b = " ".join(w_list[:MAX_BULLET_WORDS])
                        if clean_b:
                            sanitized_bullets.append(clean_b)
                    elif isinstance(b, dict):
                        sanitized_bullets.append(str(b.get("text") or b.get("value") or b))
                slide["bullets"] = sanitized_bullets

            # 3. Sanitize Table if present
            table = slide.get("table")
            if isinstance(table, dict):
                headers = table.get("headers") or table.get("header") or []
                rows = table.get("rows") or []
                if len(headers) > MAX_TABLE_COLS:
                    headers = headers[:MAX_TABLE_COLS]
                    table["headers"] = headers
                if len(rows) > MAX_TABLE_ROWS:
                    rows = rows[:MAX_TABLE_ROWS]
                # Ensure each row length matches headers
                sanitized_rows = []
                for r in rows:
                    if isinstance(r, list):
                        row_cells = [str(c)[:50] for c in r[:len(headers)]]
                        while len(row_cells) < len(headers):
                            row_cells.append("-")
                        sanitized_rows.append(row_cells)
                table["rows"] = sanitized_rows

            # 4. Enforce Layout Variety Anti-Repetition
            layout = str(slide.get("layoutHint") or slide.get("layout") or "")
            if recent_layouts and layout and layout == recent_layouts[-1] and layout not in ("section_divider", "divider"):
                # Rotate to an alternate variety candidate
                variety_alternates = ["two_column", "card_grid", "process_steps", "comparison", "stat_trio", "timeline_h"]
                alt = next((a for a in variety_alternates if a != layout and recent_layouts.count(a) < MAX_SAME_LAYOUT), "two_column")
                slide["layoutHint"] = alt
                slide["layout"] = alt
                layout = alt
            recent_layouts.append(layout)

        return spec
