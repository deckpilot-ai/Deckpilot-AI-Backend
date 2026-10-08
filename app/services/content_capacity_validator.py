"""Pre-Render Content Capacity Validation and Adaptation Service.

Validates text volume and structure against layout archetype constraints
BEFORE PowerPoint compilation to prevent clipping, overflow, and layout mismatches.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.schemas.generation_state import DesignSystem, LayoutFamily, SlideSpec
from app.services.design_system import clean_text
from app.services.text_measurement import TextMeasurementService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapacityIssue:
    slide_number: int
    issue_type: str  # "TITLE_OVERFLOW", "BODY_OVERFLOW", "UNDERFILL", "LAYOUT_MISMATCH"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    element_name: str
    message: str
    suggested_action: str


class ContentCapacityValidator:
    """Validates and adapts slide content capacity prior to rendering."""

    MAX_TITLE_WORDS = 16
    MAX_CARD_WORDS_AT_FLOOR = 32

    @classmethod
    def validate_slide(
        cls,
        slide_spec: SlideSpec,
        font_name: str = "Segoe UI",
    ) -> list[CapacityIssue]:
        """Audits slide content volume against layout capacity."""
        issues: list[CapacityIssue] = []
        slide_num = getattr(slide_spec, "slide_number", 1)
        title = clean_text(slide_spec.headline or getattr(slide_spec, "key_message", "") or "")
        bullets = [clean_text(b) for b in (slide_spec.bullets or []) if clean_text(b)]
        layout = getattr(slide_spec, "layout_family", None)
        arch_id = str(getattr(slide_spec, "archetype_id", "") or "")

        # 1. Title Audit
        if title:
            title_fits, rec_size, lines = TextMeasurementService.measure_title_fits(
                title, max_width_in=12.133, max_height_in=1.15, font_name=font_name
            )
            if not title_fits or len(title.split()) > cls.MAX_TITLE_WORDS:
                issues.append(
                    CapacityIssue(
                        slide_number=slide_num,
                        issue_type="TITLE_OVERFLOW",
                        severity="HIGH",
                        element_name="title",
                        message=f"Title ({len(title.split())} words, {len(lines)} lines) exceeds recommended 2-line title budget",
                        suggested_action="shorten_title",
                    )
                )

        # 2. Bullet count & volume vs Layout Audit
        total_bullet_words = sum(len(b.split()) for b in bullets)
        num_bullets = len(bullets)

        if num_bullets == 0 and not slide_spec.image_artifact_id and not slide_spec.table_spec and not slide_spec.chart_spec:
            issues.append(
                CapacityIssue(
                    slide_number=slide_num,
                    issue_type="UNDERFILL",
                    severity="HIGH",
                    element_name="body",
                    message="Slide has no bullet points or visual assets",
                    suggested_action="add_content_or_merge",
                )
            )

        # Multi-card layout capacity checks
        if layout in (LayoutFamily.CARD_GRID, LayoutFamily.THREE_COLUMN) or arch_id in ("A10", "A11", "A13"):
            card_count = num_bullets
            if card_count > 0:
                max_words = max(len(b.split()) for b in bullets)
                if max_words > cls.MAX_CARD_WORDS_AT_FLOOR:
                    issues.append(
                        CapacityIssue(
                            slide_number=slide_num,
                            issue_type="BODY_OVERFLOW",
                            severity="CRITICAL" if max_words > 60 else "HIGH",
                            element_name="bullets",
                            message=f"Longest bullet contains {max_words} words, which risks card container overflow at 11pt",
                            suggested_action="shorten_and_reflow",
                        )
                    )

            if num_bullets > 6 and arch_id in ("A10", "A11"):
                issues.append(
                    CapacityIssue(
                        slide_number=slide_num,
                        issue_type="LAYOUT_MISMATCH",
                        severity="HIGH",
                        element_name="layout",
                        message=f"Layout {arch_id} is designed for 3-4 items, but slide has {num_bullets} bullets",
                        suggested_action="adapt_layout_to_content",
                    )
                )

        return issues

    @classmethod
    def check_layout_fit(cls, slide_spec: SlideSpec, layout_family: Any) -> str:
        """Quick check for storyline planning: returns 'OK', 'OVERFLOW', or 'UNDERFILL'."""
        bullets = [clean_text(b) for b in (slide_spec.bullets or []) if clean_text(b)]
        num_bullets = len(bullets)
        total_words = sum(len(b.split()) for b in bullets)

        if num_bullets == 0 and not slide_spec.image_artifact_id:
            return "UNDERFILL"

        if layout_family in (LayoutFamily.TWO_COLUMN, LayoutFamily.A7_TWO_COLUMN_CONTRAST):
            if num_bullets > 6 or total_words > 120:
                return "OVERFLOW"
        elif layout_family in (LayoutFamily.THREE_COLUMN, LayoutFamily.A11_STAGE_COLUMNS, LayoutFamily.A10_NUMBERED_PROCESS):
            if num_bullets > 4 or total_words > 90:
                return "OVERFLOW"
        elif layout_family in (LayoutFamily.CARD_GRID, LayoutFamily.A13_ICON_GRID):
            if num_bullets > 6 or total_words > 140:
                return "OVERFLOW"

        return "OK"

    @classmethod
    def shorten_phrase_intelligently(cls, text: str, max_words: int = 18) -> str:
        """Shortens text at natural syntactic boundaries (clauses, colons, punctuation)."""
        cleaned = clean_text(text)
        words = cleaned.split()
        if len(words) <= max_words:
            return cleaned

        # Try cutting at colon if present
        if ":" in cleaned:
            lead, remainder = cleaned.split(":", 1)
            rem_words = remainder.strip().split()
            avail = max_words - len(lead.split())
            if avail >= 4:
                return f"{lead.strip()}: {' '.join(rem_words[:avail]).rstrip(' ,;:-')}."

        # Try cutting at sentence punctuation (. ; ,) within range
        joined = " ".join(words[:max_words])
        match = re.search(r"^(.*[.!?])\s+", joined)
        if match and len(match.group(1).split()) >= max_words // 2:
            return match.group(1).strip()

        # Fallback to word boundary
        return " ".join(words[:max_words]).rstrip(" ,;:-") + "."

    @classmethod
    def shorten_title_intelligently(cls, title: str, max_words: int = 12) -> str:
        """Shortens title cleanly preserving the core predicate."""
        cleaned = clean_text(title)
        words = cleaned.split()
        if len(words) <= max_words:
            return cleaned

        if ":" in cleaned:
            parts = cleaned.split(":", 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip()
            # If prefix is informative, keep it with shortened suffix
            if 2 <= len(prefix.split()) <= 6:
                avail = max_words - len(prefix.split())
                short_suf = " ".join(suffix.split()[:avail]).rstrip(" ,;:-")
                return f"{prefix}: {short_suf}"

        # Natural boundary trimming
        candidate = " ".join(words[:max_words]).rstrip(" ,;:-")
        return candidate

    @classmethod
    def validate_and_fix(
        cls,
        slide_specs: list[SlideSpec],
        design_system: DesignSystem | None = None,
    ) -> list[SlideSpec]:
        """Pre-validates and optimizes all slides prior to rendering."""
        font_name = design_system.typography.body_font.name if design_system else "Segoe UI"
        title_font = design_system.typography.title_font.name if design_system else "Segoe UI"

        for slide in slide_specs:
            if not hasattr(slide, "archetype_fields") or slide.archetype_fields is None:
                slide.archetype_fields = {}

            # 1. Headline / Title Optimization
            raw_title = clean_text(slide.headline or getattr(slide, "key_message", "") or "")
            if raw_title:
                title_words = len(raw_title.split())
                if title_words > cls.MAX_TITLE_WORDS:
                    slide.headline = cls.shorten_title_intelligently(raw_title, max_words=12)

            # 2. Bullets Optimization & Trimming
            bullets = [clean_text(b) for b in (slide.bullets or []) if clean_text(b)]
            layout = getattr(slide, "layout_family", None)
            arch_id = str(getattr(slide, "archetype_id", "") or "")

            if bullets:
                # Progressive bullet shortening for cards
                max_bullet_words = 28 if len(bullets) <= 3 else (22 if len(bullets) <= 4 else 18)
                fixed_bullets = []
                for b in bullets:
                    if len(b.split()) > max_bullet_words:
                        fixed_bullets.append(cls.shorten_phrase_intelligently(b, max_words=max_bullet_words))
                    else:
                        fixed_bullets.append(b)
                slide.bullets = fixed_bullets

                # 3. Layout Adaptation for Bullet Count Mismatches
                num_bullets = len(fixed_bullets)
                if num_bullets == 4 and layout in (LayoutFamily.TWO_COLUMN, LayoutFamily.A7_TWO_COLUMN_CONTRAST):
                    # 4 bullets fit much better in a 2x2 CARD_GRID than a 2-column split
                    slide.layout_family = LayoutFamily.CARD_GRID
                    slide.archetype_id = "A13"
                    slide.layout_hint = "card_grid"
                elif num_bullets in (6, 7, 8) and layout in (LayoutFamily.THREE_COLUMN, LayoutFamily.A11_STAGE_COLUMNS, LayoutFamily.A10_NUMBERED_PROCESS):
                    # 6-8 bullets in 3 columns overcrowds; route to 8-feature Council grid
                    slide.layout_family = LayoutFamily.COUNCIL_EIGHT
                    slide.archetype_id = "A25"
                    slide.layout_hint = "council_eight"
                elif num_bullets <= 2 and layout == LayoutFamily.CARD_GRID and not slide.image_artifact_id:
                    # 2 bullets in a card grid look sparse; route to two-column
                    slide.layout_family = LayoutFamily.TWO_COLUMN
                    slide.archetype_id = "A7"
                    slide.layout_hint = "two_column"

                # 4. Underfill font boost
                total_words = sum(len(b.split()) for b in fixed_bullets)
                if num_bullets <= 3 and total_words <= 30 and not slide.image_artifact_id:
                    slide.archetype_fields["qa_font_scale"] = 1.15

        return slide_specs
