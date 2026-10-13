"""Development Editorial Theme Definition and Master Dispatcher.

Integrates tokens, typography, components, and layout composers into a unified
reusable theme for DeckPilot AI.
"""

import logging
from typing import Any, Dict, Optional

from app.presentation.themes.development_editorial.tokens import COLORS, FONTS, SHADOWS, SPACING
from app.presentation.themes.development_editorial.layouts import LayoutComposers

logger = logging.getLogger(__name__)


class DevelopmentEditorialTheme:
    """The canonical Development Editorial Presentation Theme."""

    THEME_ID = "development-editorial-v1"
    NAME = "Development Editorial Theme"

    colors = COLORS
    fonts = FONTS
    shadows = SHADOWS
    spacing = SPACING

    _DISPATCH_MAP = {
        "L01": LayoutComposers.render_l01,
        "L02": LayoutComposers.render_l02,
        "L03": LayoutComposers.render_l03,
        "L04": LayoutComposers.render_l04,
        "L05": LayoutComposers.render_l05,
        "L06": LayoutComposers.render_l06,
        "L07": LayoutComposers.render_l07,
        "L08": LayoutComposers.render_l08,
        "L09": LayoutComposers.render_l09,
        "L10": LayoutComposers.render_l10,
        "L11": LayoutComposers.render_l11,
        "L12": LayoutComposers.render_l12,
        "L13": LayoutComposers.render_l13,
        "L14": LayoutComposers.render_l14,
        "L15": LayoutComposers.render_l15,
        "L16": LayoutComposers.render_l16,
        "L17": LayoutComposers.render_l17,
        "L18": LayoutComposers.render_l18,
        "L19": LayoutComposers.render_l19,
        "L20": LayoutComposers.render_l20,
        "L21": LayoutComposers.render_l21,
        "L22": LayoutComposers.render_l22,
        "L23": LayoutComposers.render_l23,
        "L_TIMELINE": LayoutComposers.render_timeline,
        # Legacy / Alias mappings for compatibility
        "COVER": LayoutComposers.render_l01,
        "HERO": LayoutComposers.render_l01,
        "AGENDA": LayoutComposers.render_l02,
        "ROADMAP": LayoutComposers.render_l02,
        "CONCEPT": LayoutComposers.render_l03,
        "TABLE": LayoutComposers.render_l04,
        "PROCESS": LayoutComposers.render_l09,
        "METRICS": LayoutComposers.render_l10,
        "STATISTICS": LayoutComposers.render_l10,
        "CHART": LayoutComposers.render_l11,
        "SECTION": LayoutComposers.render_l18,
        "SUMMARY": LayoutComposers.render_l22,
        "TAKEAWAYS": LayoutComposers.render_l22,
        "CLOSING": LayoutComposers.render_l23,
        "TIMELINE": LayoutComposers.render_timeline,
    }

    @classmethod
    def supports_layout(cls, layout_id: str) -> bool:
        return str(layout_id).upper() in cls._DISPATCH_MAP

    @classmethod
    def render_slide(cls, slide: Any, layout_id: str, data: Dict[str, Any], images: Optional[Dict[str, bytes]] = None) -> bool:
        """Renders slide using the mapped editorial composer."""
        key = str(layout_id).upper()
        composer = cls._DISPATCH_MAP.get(key)
        if not composer:
            logger.warning("Layout %s not supported in %s; falling back to L03", layout_id, cls.NAME)
            composer = LayoutComposers.render_l03

        img_dict = images or {}
        try:
            composer(slide, data, img_dict)
            return True
        except Exception as e:
            logger.error("Error rendering layout %s in %s: %s", layout_id, cls.NAME, e, exc_info=True)
            return False
