"""Deterministic and Explainable Layout Selector with Presentation Layout Memory.

Scores registered layout archetypes against slide semantic signals to select the
most art-directed and context-appropriate slide design, enforcing anti-repetition rules.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.presentation.layout.layout_registry import LAYOUT_REGISTRY, LayoutMetadata
from app.presentation.layout.content_classifier import ContentClassifier, SlideSignals

logger = logging.getLogger(__name__)


class PresentationLayoutMemory:
    """Tracks sequence of chosen layouts across a presentation to enforce rhythm and variety."""

    def __init__(self):
        self.history: List[str] = []
        self.family_history: List[str] = []
        self.dark_slide_count: int = 0
        self.image_slide_count: int = 0

    def record(self, layout_id: str, family: str = "", is_dark: bool = False, has_image: bool = False):
        self.history.append(layout_id)
        self.family_history.append(family)
        if is_dark:
            self.dark_slide_count += 1
        if has_image:
            self.image_slide_count += 1

    def penalty_for(self, layout_id: str, family: str = "") -> float:
        penalty = 0.0
        # Block consecutive repetition of identical archetype
        if self.history and self.history[-1] == layout_id:
            penalty += 120.0

        # Discourage consecutive slides of same layout family
        if self.family_history and family and self.family_history[-1] == family:
            penalty += 30.0

        # Discourage using same layout > 2 times within 10 slides
        recent_10 = self.history[-10:]
        if recent_10.count(layout_id) >= 2:
            penalty += 50.0

        return penalty


class SemanticLayoutSelector:
    """Intelligent layout selector supporting multiple design systems."""

    @classmethod
    def select(
        cls,
        slide_data: Dict[str, Any],
        slide_index: int = 0,
        total_slides: int = 1,
        theme_id: str = "federalism-editorial-v1",
        memory: Optional[PresentationLayoutMemory] = None,
        signals: Optional[SlideSignals] = None
    ) -> Dict[str, Any]:
        """Returns structured layout selection result with alternatives and confidence."""
        if signals is None:
            signals = ContentClassifier.classify(slide_data, slide_index, total_slides)

        prefix = "F" if "federalism" in theme_id.lower() else "L"
        # Filter candidate layouts by theme prefix
        candidates = {
            lid: meta for lid, meta in LAYOUT_REGISTRY.items()
            if lid.startswith(prefix)
        }
        if not candidates:
            candidates = LAYOUT_REGISTRY

        scores: List[Tuple[float, str, str]] = []

        for lid, meta in candidates.items():
            score = 0.0
            reasons: List[str] = []

            # 1. Hard Intent Matching
            if signals.slide_intent == "cover":
                if lid in ("F01", "L01"):
                    score += 200.0
                    reasons.append("Designated Cover Hero archetype")
                else:
                    continue

            elif signals.slide_intent == "closing":
                if lid in ("F24", "L23"):
                    score += 200.0
                    reasons.append("Designated Closing Hero archetype")
                else:
                    continue

            elif signals.slide_intent == "agenda":
                if lid in ("F02", "L02"):
                    score += 90.0
                    reasons.append("Agenda/roadmap intent match")

            elif signals.slide_intent == "summary":
                if lid in ("F23", "L22"):
                    score += 90.0
                    reasons.append("Summary/takeaways intent match")

            elif signals.slide_intent == "timeline":
                if lid in ("F25", "F26", "F27", "L_TIMELINE"):
                    score += 95.0
                    reasons.append("Chronology/milestones signal matches timeline")

            elif signals.slide_intent == "section_opener":
                if lid in ("F13", "L18", "L21"):
                    score += 80.0
                    reasons.append("Section opener/dark divider intent")

            # 2. Asset Constraints Matching
            if signals.has_table:
                if meta.supports_table:
                    score += 40.0
                    reasons.append("Supports table asset")
                else:
                    score -= 60.0

            if signals.has_chart:
                if meta.supports_chart:
                    score += 40.0
                    reasons.append("Supports chart asset")
                else:
                    score -= 60.0

            if signals.has_image:
                if meta.requires_image:
                    score += 25.0
                    reasons.append("Provides designated frame for image")
            else:
                if meta.requires_image:
                    score -= 50.0
                    reasons.append("Penalized: requires image but none provided")

            # 3. Item Count Alignment
            if meta.min_items <= signals.item_count <= meta.max_items:
                score += 15.0
                reasons.append(f"Item count {signals.item_count} fits [{meta.min_items}, {meta.max_items}]")
            elif signals.item_count > meta.max_items:
                score -= 30.0

            # 4. Feature Affinity
            if signals.has_process and meta.supports_process:
                score += 30.0
                reasons.append("Process/tier workflow structure matches")

            if signals.has_statistics and meta.supports_stats:
                score += 30.0
                reasons.append("Prominent metrics match KPI archetype")

            if signals.has_quote and meta.supports_quote:
                score += 20.0
                reasons.append("Editorial quote card accommodated")

            if signals.has_comparison and meta.family in ("comparison", "split_comparison", "before_after"):
                score += 30.0
                reasons.append("Comparative structure matches comparison layout")

            if signals.is_dark_preferred and meta.is_dark:
                score += 20.0
                reasons.append("Dark canvas matches section mood")
            elif not signals.is_dark_preferred and meta.is_dark and signals.slide_intent not in ("cover", "closing", "section_opener"):
                score -= 25.0

            # 5. Anti-Repetition Penalty from Memory
            if memory:
                pen = memory.penalty_for(lid, meta.family)
                if pen > 0:
                    score -= pen
                    reasons.append(f"Repetition penalty (-{pen:.0f})")

            exp = "; ".join(reasons) if reasons else "Compatible layout"
            scores.append((score, lid, exp))

        scores.sort(key=lambda x: x[0], reverse=True)
        best_score, best_lid, best_exp = scores[0] if scores else (0.0, "F03" if prefix == "F" else "L03", "Fallback")
        alts = [item[1] for item in scores[1:4]]

        confidence = max(0.5, min(0.99, best_score / 120.0)) if best_score > 0 else 0.5
        if memory and best_lid in candidates:
            meta = candidates[best_lid]
            memory.record(best_lid, meta.family, meta.is_dark, meta.requires_image)

        return {
            "selected_layout": best_lid,
            "confidence": round(confidence, 2),
            "reasoning": best_exp,
            "alternative_layouts": alts
        }


class LayoutSelector:
    """Legacy backward-compatible wrapper around SemanticLayoutSelector."""

    @classmethod
    def select_layout(
        cls,
        slide_data: Dict[str, Any],
        slide_index: int = 0,
        total_slides: int = 1,
        signals: Optional[SlideSignals] = None,
        theme_id: str = "federalism-editorial-v1"
    ) -> Tuple[str, str]:
        """Returns (layout_id, explanation)."""
        res = SemanticLayoutSelector.select(
            slide_data,
            slide_index=slide_index,
            total_slides=total_slides,
            theme_id=theme_id,
            signals=signals
        )
        return (res["selected_layout"], res["reasoning"])
