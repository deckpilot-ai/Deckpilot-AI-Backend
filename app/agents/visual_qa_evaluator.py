"""AI-Guided Visual QA Evaluator & Slide Strategy Engine.

Analyzes presentation slides for visual rhythm, box pattern repetition,
content-to-box geometry balance, and visual asset pacing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.qa_checkpoints import CHECKPOINT_BY_ID, CHECKPOINT_ID_BY_SLUG
from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


class VisualQAEvaluator:
    """Evaluates slide visual architecture, anti-repetition, and box geometry."""

    @classmethod
    def evaluate_slide_visual_strategy(
        cls,
        slides: list[SlideSpec],
        design_system: DesignSystem,
        available_assets: list[AssetMetadata] | None = None,
    ) -> list[ValidationIssue]:
        """Runs strategic visual layout and diversity checks across all slides."""
        issues: list[ValidationIssue] = []
        assets = available_assets or []
        total_slides = len(slides)

        if not slides:
            return issues

        # 1. Check Visual Asset Allocation Ratio
        if assets and total_slides >= 4:
            image_slides = sum(1 for s in slides if s.image_artifact_id)
            target_visual_count = min(len(assets), max(2, int((total_slides - 2) * 0.40)))
            if image_slides < target_visual_count and len(assets) >= 2:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("sparse_visual_pacing", "QA-074"),
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.DESIGN,
                        slide_number=1,
                        slide_id=slides[0].slide_id,
                        message=f"Visual asset underutilization: only {image_slides} of {target_visual_count} recommended visual slides have images assigned despite {len(assets)} available PDF assets",
                        suggested_fix="Dynamically distribute available documentary assets across content slides to reach 35-50% visual pacing ratio",
                        auto_fixable=True,
                        repair_action="assign_visuals",
                    )
                )

        # 2. Check Repetitive Box Pattern / Duplicate Slide Shapes
        for idx in range(1, len(slides)):
            curr = slides[idx]
            prev = slides[idx - 1]

            # Check consecutive identical layout families for box/column layouts
            box_layouts = {
                LayoutFamily.TWO_COLUMN,
                LayoutFamily.CARD_GRID,
                LayoutFamily.THREE_COLUMN,
                LayoutFamily.COMPARISON,
            }
            if curr.layout_family in box_layouts and prev.layout_family == curr.layout_family:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("consecutive_same_layout", "QA-077"),
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.DESIGN,
                        slide_number=idx + 1,
                        slide_id=curr.slide_id,
                        message=f"Repetitive box pattern on Slide {idx + 1}: duplicate '{curr.layout_family.value}' layout immediately follows Slide {idx}",
                        suggested_fix="Differentiate layout by switching to a contrasting archetype (e.g. process flow A10, comparison A6, or stat cluster A21)",
                        auto_fixable=True,
                        repair_action="change_layout",
                    )
                )

            # Check identical archetype ID repetition
            if curr.archetype_id and prev.archetype_id and curr.archetype_id == prev.archetype_id and idx > 1:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("consecutive_same_layout", "QA-077"),
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.DESIGN,
                        slide_number=idx + 1,
                        slide_id=curr.slide_id,
                        message=f"Repetitive archetype {curr.archetype_id} across consecutive Slides {idx} and {idx + 1}",
                        suggested_fix="Rotate to an alternate consulting archetype to maintain presentation rhythm",
                        auto_fixable=True,
                        repair_action="change_layout",
                    )
                )

        # 3. Check Box Content vs Box Geometry (One-Liner Empty Box Detection)
        for idx, slide in enumerate(slides, 1):
            if idx == 1 or slide.layout_family in (LayoutFamily.HERO, LayoutFamily.CLOSING, LayoutFamily.SECTION_DIVIDER):
                continue

            bullets = [b for b in slide.bullets if isinstance(b, str) and b.strip()]
            if not bullets and not slide.takeaway and not slide.image_artifact_id and not slide.chart_spec and not slide.table_spec:
                continue

            # If slide has 1-3 short bullets where each bullet is <= 10 words, standard tall cards create huge empty boxes
            if bullets and len(bullets) <= 3 and all(len(str(b).split()) <= 10 for b in bullets):
                if slide.layout_family in (LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID):
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("excessive_blank_space", "QA-049"),
                            severity=ValidationSeverity.MEDIUM,
                            category=ValidationCategory.GEOMETRY,
                            slide_number=idx,
                            slide_id=slide.slide_id,
                            message=f"Slide {idx} contains concise one-liner bullets in an oversized box layout, creating excessive empty box void",
                            suggested_fix="Rebalance card geometry with elevated typography, balanced padding, and top key idea banner",
                            auto_fixable=True,
                            repair_action="rebalance_layout",
                        )
                    )

        return issues
