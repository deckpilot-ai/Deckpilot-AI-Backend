"""Presentation-Level QA Agent for whole-deck rhythm, layout repetition, and source grounding."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agents.qa_checkpoints import CHECKPOINT_ID_BY_SLUG
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


class PresentationLevelQA:
    """Evaluates multi-slide deck coherence, layout diversity, visual pacing, and reference source coverage."""

    @classmethod
    def evaluate_deck(
        cls,
        slides: list[SlideSpec],
        design_system: DesignSystem,
        available_assets: list[AssetMetadata] | None = None,
        source_texts: list[str] | None = None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        n_slides = len(slides)
        if n_slides == 0:
            return issues

        # 1. Consecutive Same Layout Check
        for i in range(n_slides - 2):
            l1 = slides[i].layout_family or slides[i].layout_hint
            l2 = slides[i + 1].layout_family or slides[i + 1].layout_hint
            l3 = slides[i + 2].layout_family or slides[i + 2].layout_hint
            if l1 and l1 == l2 == l3:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("consecutive_same_layout", "QA-077"),
                        severity=ValidationSeverity.HIGH,
                        category=ValidationCategory.DESIGN,
                        slide_number=i + 3,
                        slide_id=slides[i + 2].slide_id,
                        message=f"Layout '{l1}' is repeated 3 times consecutively on Slides {i+1}, {i+2}, and {i+3}",
                        suggested_fix="Vary slide layout to maintain audience engagement and visual rhythm",
                        auto_fixable=True,
                        repair_action="vary_layout",
                    )
                )

        # 2. Overall Layout Diversity Check (for decks with 6+ slides)
        if n_slides >= 6:
            unique_layouts = {s.layout_family or s.layout_hint for s in slides if s.layout_family or s.layout_hint}
            min_expected_layouts = min(4, max(2, n_slides // 3))
            if len(unique_layouts) < min_expected_layouts:
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("consecutive_same_layout", "QA-077"),
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.DESIGN,
                        slide_number=1,
                        message=f"Deck lacks layout diversity ({len(unique_layouts)} unique layouts across {n_slides} slides; expected at least {min_expected_layouts})",
                        suggested_fix="Introduce varied card grids, split columns, or quote archetypes",
                        auto_fixable=True,
                        repair_action="vary_layout",
                    )
                )

        # 3. Visual Pacing & Image Utilization
        image_slides = sum(1 for s in slides if s.image_artifact_id or s.layout_family in (
            LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE, LayoutFamily.A2_TITLE_SPLIT, LayoutFamily.A8_STAT_IMAGE_HIGHLIGHT
        ))
        has_assets = bool(available_assets and len(available_assets) > 0)

        if has_assets and image_slides == 0 and n_slides >= 5:
            issues.append(
                ValidationIssue(
                    checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("no_visuals", "QA-073"),
                    severity=ValidationSeverity.HIGH,
                    category=ValidationCategory.DESIGN,
                    slide_number=1,
                    message=f"Deck contains no visual or image-led slides despite {len(available_assets)} source assets available",
                    suggested_fix="Assign high-relevance source images to appropriate content slides",
                    auto_fixable=True,
                    repair_action="assign_visuals",
                )
            )

        # Consecutive image slides check (avoid fatigue of 3 consecutive photo spreads)
        for i in range(n_slides - 2):
            if all(bool(slides[i + j].image_artifact_id) for j in range(3)):
                issues.append(
                    ValidationIssue(
                        checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("consecutive_image_layouts", "QA-076"),
                        severity=ValidationSeverity.MEDIUM,
                        category=ValidationCategory.DESIGN,
                        slide_number=i + 3,
                        slide_id=slides[i + 2].slide_id,
                        message=f"Three consecutive image-heavy slides on Slides {i+1} through {i+3}",
                        suggested_fix="Alternate with a structured data card or analytical table",
                        auto_fixable=True,
                        repair_action="vary_layout",
                    )
                )

        # 4. Source Utilization Grounding Ratio
        if source_texts:
            all_source = " ".join(source_texts).lower()
            # Extract key capitalized entities / noun phrases from source
            keywords = set(re.findall(r"\b[a-z]{5,}\b", all_source))
            if len(keywords) > 20:
                deck_text = " ".join(
                    f"{s.headline} {' '.join(s.bullets)} {s.takeaway}"
                    for s in slides
                ).lower()
                deck_words = set(re.findall(r"\b[a-z]{5,}\b", deck_text))
                common_terms = keywords.intersection(deck_words)
                utilization = len(common_terms) / min(len(keywords), 150)

                if utilization < 0.25 and n_slides >= 5:
                    issues.append(
                        ValidationIssue(
                            checkpoint_id=CHECKPOINT_ID_BY_SLUG.get("unused_relevant_image", "QA-065"),
                            severity=ValidationSeverity.HIGH,
                            category=ValidationCategory.CONTENT,
                            slide_number=1,
                            message=f"Low reference document grounding ({utilization:.1%} vocabulary alignment); presentation appears too generic",
                            suggested_fix="Ground narrative more deeply in specific reference document data and facts",
                            auto_fixable=True,
                            repair_action="expand_layout",
                        )
                    )

        return issues
