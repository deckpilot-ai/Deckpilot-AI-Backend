"""Federalism Editorial Theme Definition and Master Dispatcher.

Integrates tokens, typography, components, and layout composers into a unified
reusable theme for DeckPilot AI modeled on Federalism (2).pptx.
"""

import logging
from typing import Any, Dict, Optional

from app.presentation.themes.federalism_editorial.tokens import COLORS, FONTS, SHADOWS, SPACING, GEOMETRY
from app.presentation.themes.federalism_editorial.layouts import FederalismLayouts

logger = logging.getLogger(__name__)


class FederalismEditorialTheme:
    """The canonical Federalism Editorial Presentation Theme."""

    THEME_ID = "federalism-editorial-v1"
    NAME = "Federalism Editorial Theme"

    colors = COLORS
    fonts = FONTS
    shadows = SHADOWS
    spacing = SPACING
    geometry = GEOMETRY

    _DISPATCH_MAP = {
        "F01": FederalismLayouts.render_f01,
        "F02": FederalismLayouts.render_f02,
        "F03": FederalismLayouts.render_f03,
        "F04": FederalismLayouts.render_f04,
        "F05": FederalismLayouts.render_f05,
        "F06": FederalismLayouts.render_f06,
        "F07": FederalismLayouts.render_f07,
        "F08": FederalismLayouts.render_f08,
        "F09": FederalismLayouts.render_f09,
        "F10": FederalismLayouts.render_f10,
        "F11": FederalismLayouts.render_f11,
        "F12": FederalismLayouts.render_f12,
        "F13": FederalismLayouts.render_f13,
        "F14": FederalismLayouts.render_f14,
        "F15": FederalismLayouts.render_f15,
        "F16": FederalismLayouts.render_f16,
        "F17": FederalismLayouts.render_f17,
        "F18": FederalismLayouts.render_f18,
        "F19": FederalismLayouts.render_f19,
        "F20": FederalismLayouts.render_f20,
        "F21": FederalismLayouts.render_f21,
        "F22": FederalismLayouts.render_f22,
        "F23": FederalismLayouts.render_f23,
        "F24": FederalismLayouts.render_f24,
        "F25": FederalismLayouts.render_f25,
        "F26": FederalismLayouts.render_f26,
        "F27": FederalismLayouts.render_f27,
        # Semantic & fallback aliases
        "COVER": FederalismLayouts.render_f01,
        "HERO": FederalismLayouts.render_f01,
        "ROADMAP": FederalismLayouts.render_f02,
        "AGENDA": FederalismLayouts.render_f02,
        "DEFINITION": FederalismLayouts.render_f03,
        "CONCEPT": FederalismLayouts.render_f03,
        "FRAMEWORK": FederalismLayouts.render_f03,
        "COMPARISON": FederalismLayouts.render_f04,
        "DUAL": FederalismLayouts.render_f04,
        "METRICS": FederalismLayouts.render_f05,
        "MAP": FederalismLayouts.render_f05,
        "SPLIT_LIST": FederalismLayouts.render_f06,
        "GRID": FederalismLayouts.render_f07,
        "FEATURES": FederalismLayouts.render_f07,
        "CATEGORIES": FederalismLayouts.render_f08,
        "TIERS": FederalismLayouts.render_f09,
        "THREE_TIERS": FederalismLayouts.render_f09,
        "THREE_LISTS": FederalismLayouts.render_f10,
        "DETAIL": FederalismLayouts.render_f11,
        "PROCESS": FederalismLayouts.render_f12,
        "STEPS": FederalismLayouts.render_f12,
        "SECTION": FederalismLayouts.render_f13,
        "TRANSITION": FederalismLayouts.render_f13,
        "INSIGHTS": FederalismLayouts.render_f14,
        "QUOTE": FederalismLayouts.render_f15,
        "FOUR_GRID": FederalismLayouts.render_f16,
        "CHART": FederalismLayouts.render_f17,
        "BEFORE_AFTER": FederalismLayouts.render_f18,
        "REASONS": FederalismLayouts.render_f19,
        "REFORMS": FederalismLayouts.render_f20,
        "HIERARCHY": FederalismLayouts.render_f21,
        "ORGANIZATION": FederalismLayouts.render_f21,
        "IMPACT": FederalismLayouts.render_f22,
        "CHALLENGES": FederalismLayouts.render_f22,
        "SUMMARY": FederalismLayouts.render_f23,
        "TAKEAWAYS": FederalismLayouts.render_f23,
        "CLOSING": FederalismLayouts.render_f24,
        "TIMELINE": FederalismLayouts.render_f25,
        "TIMELINE_HORIZONTAL": FederalismLayouts.render_f25,
        "TIMELINE_VERTICAL": FederalismLayouts.render_f26,
        "TIMELINE_ERA": FederalismLayouts.render_f27,
    }

    @classmethod
    def supports_layout(cls, layout_id: str) -> bool:
        return str(layout_id).upper() in cls._DISPATCH_MAP

    @classmethod
    def render_slide(cls, slide: Any, layout_id: str, data: Dict[str, Any], images: Optional[Dict[str, bytes]] = None) -> bool:
        """Renders slide using the mapped Federalism editorial composer."""
        key = str(layout_id).upper()
        composer = cls._DISPATCH_MAP.get(key)
        if not composer:
            logger.warning("Layout %s not supported in %s; falling back to F03", layout_id, cls.NAME)
            composer = FederalismLayouts.render_f03

        img_dict = images or {}
        try:
            composer(slide, data, img_dict)
            return True
        except Exception as e:
            logger.error("Error rendering layout %s in %s: %s", layout_id, cls.NAME, e, exc_info=True)
            return False
