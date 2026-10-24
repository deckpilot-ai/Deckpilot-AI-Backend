"""Automated Repair Agent for Slide Remediation.

Iteratively corrects QA failures (e.g. title overflow, text truncation, missing images,
table overload, icon failures) and triggers re-rendering with adjusted constraints.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.presentation.qa.visual_qa import QAReport, QAViolation, VisualQAAgent

try:
    from app.presentation.themes.federalism_editorial.typography import TitleOptimizer
    def normalize_title(text: str, max_words: int = 4):
        return TitleOptimizer.optimize(text, max_words=max_words)
except ImportError:
    try:
        from app.presentation.themes.development_editorial.typography import normalize_title
    except ImportError:
        def normalize_title(text: str, max_words: int = 4):
            words = text.split()
            if len(words) <= max_words:
                return (text, "")
            return (" ".join(words[:max_words]), " ".join(words[max_words:]))

logger = logging.getLogger(__name__)


class PresentationRepairAgent:
    """Remediates slide specification failures before and after rendering."""

    MAX_REPAIR_ITERATIONS = 4

    @classmethod
    def repair_slide_spec(cls, slide_spec: Dict[str, Any], violations: List[QAViolation]) -> Dict[str, Any]:
        """Applies deterministic content and layout transformations to fix reported violations."""
        repaired = dict(slide_spec)
        applied_fixes = []

        for v in violations:
            # Fix 1: TITLE_TOO_LONG / EMPTY_TITLE
            if v.rule_id == "TITLE_TOO_LONG":
                raw_title = repaired.get("title") or repaired.get("headline") or ""
                main_title, sub_title = normalize_title(raw_title, max_words=4)
                repaired["title"] = main_title
                repaired["headline"] = main_title
                if sub_title and not repaired.get("subtitle") and not repaired.get("lead"):
                    repaired["lead"] = sub_title
                applied_fixes.append(f"Shortened title to impactful words: '{main_title}'")

            elif v.rule_id == "EMPTY_TITLE":
                repaired["title"] = "Key Insights"
                repaired["headline"] = "Key Insights"
                applied_fixes.append("Supplied default title for empty title violation")

            # Fix 2: MISSING_IMAGE / EMPTY_FRAME
            elif v.rule_id in ("MISSING_IMAGE", "EMPTY_SHAPE") and "Image" in (v.shape_name or ""):
                current_layout = str(repaired.get("layout", "F03")).upper()
                if current_layout == "F05":
                    repaired["layout"] = "F22" if len(repaired.get("items", [])) >= 2 else "F16"
                    applied_fixes.append(f"Reflowed {current_layout} -> {repaired['layout']} due to missing map/image")
                elif current_layout in ("F14", "F15"):
                    repaired["layout"] = "F10" if len(repaired.get("items", [])) >= 3 else "F08"
                    applied_fixes.append(f"Reflowed {current_layout} -> {repaired['layout']} due to missing image")
                elif current_layout == "F18":
                    repaired["layout"] = "F04"
                    applied_fixes.append(f"Reflowed {current_layout} -> F04 due to missing comparison images")
                elif current_layout in ("L03", "L05"):
                    repaired["layout"] = "L02" if len(repaired.get("items", [])) >= 4 else "L10"
                    applied_fixes.append(f"Reflowed {current_layout} -> {repaired['layout']} due to missing image asset")

            # Fix 3: TABLE_OVERFLOW
            elif v.rule_id == "TABLE_OVERFLOW":
                rows = repaired.get("table_rows", [])
                if len(rows) > 7:
                    repaired["table_rows"] = rows[:7]
                    applied_fixes.append("Clamped table rows to top 7 key entries")

            # Fix 4: TINY_FONT / TEXT_OVERFLOW
            elif v.rule_id in ("TINY_FONT", "TEXT_OVERFLOW"):
                body = repaired.get("body", "")
                if len(body) > 220:
                    repaired["body"] = body[:215].rsplit(" ", 1)[0] + "..."
                    applied_fixes.append("Summarized body text to fit typography budget")

                # Summarize items if any
                items = repaired.get("items", [])
                if items and isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and "body" in item and len(item["body"]) > 160:
                            item["body"] = item["body"][:155].rsplit(" ", 1)[0] + "..."
                            applied_fixes.append("Summarized card item body to fit card container")

            # Fix 5: ICON_MISSING
            elif v.rule_id == "ICON_MISSING":
                # Ensure each item has a generic fallback icon hint
                items = repaired.get("items", [])
                for idx, itm in enumerate(items):
                    if isinstance(itm, dict) and not itm.get("icon"):
                        itm["icon"] = "check" if idx % 2 == 0 else "lightbulb"
                applied_fixes.append("Resolved fallback icons for missing icon slots")

        if applied_fixes:
            logger.info("RepairAgent applied %d fixes: %s", len(applied_fixes), "; ".join(applied_fixes))

        return repaired

    @classmethod
    def run_repair_loop(
        cls,
        slide_spec: Dict[str, Any],
        render_fn: Any,
        images: Optional[Dict[str, bytes]] = None,
        max_passes: int = MAX_REPAIR_ITERATIONS
    ) -> Tuple[Any, QAReport]:
        """Iteratively renders, inspects, and repairs until clean or max passes reached."""
        current_spec = dict(slide_spec)
        last_slide = None
        last_report = None

        for pass_num in range(1, max_passes + 1):
            slide = render_fn(current_spec, images)
            report = VisualQAAgent.inspect_slide(slide)
            last_slide = slide
            last_report = report

            if report.passed and not report.violations:
                logger.debug("Slide passed QA cleanly on pass %d", pass_num)
                return (slide, report)

            if not report.has_critical and pass_num > 1:
                return (slide, report)

            # Perform repair for next pass
            current_spec = cls.repair_slide_spec(current_spec, report.violations)

        return (last_slide, last_report)
