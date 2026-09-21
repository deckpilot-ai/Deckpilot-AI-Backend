"""Theme Registry and Semantic Layout Selector for Maratha Heritage Editorial Theme.

Registers the `maratha-heritage-editorial-v1` theme with DeckPilot AI's theme registry
and provides a historical heritage layout selector with presentation memory.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.presentation.themes.maratha_heritage_editorial.tokens import COLORS, GEOMETRY, FONTS
from app.presentation.themes.maratha_heritage_editorial import layouts

logger = logging.getLogger(__name__)

THEME_ID = "maratha-heritage-editorial-v1"
THEME_NAME = "Maratha Heritage Editorial"
THEME_CATEGORY = "heritage-editorial"


class MarathaHeritageLayoutSelector:
    """Selects the optimal layout archetype for a slide based on semantic intent.

    Priority signals:
    - cover / title slide → M01
    - questions / setting the scene → M02
    - origin / foundation / glossary → M03, M05
    - chronology / timeline phases → M04
    - navy / maritime / coastal → M06, M20
    - military / tactics / guerrilla → M07, M08, M18
    - dramatic storytelling / escape / event → M09
    - territory / map / expansion → M10
    - ethics / visionary insight → M11
    - successor / resilience / painting → M12
    - peshwas / expansion / person strip → M13
    - wars / conflict periods / quote → M14
    - civilian administration / currency → M15, M17
    - governance hub / council / ministers → M16
    - forts / fortress / core doctrine → M19
    - three pillars (justice/trade/culture) → M21
    - dual leaders / warrior queens / biographies → M22
    - cultural flowering / art gallery → M23
    - legacy / summary / takeaways → M24
    """

    PATTERNS: List[Tuple[str, List[str]]] = [
        ("M01", ["cover", "title slide", "introduction", "opening"]),
        ("M02", ["big questions", "questions", "inquiry", "setting the scene", "objectives"]),
        ("M04", ["timeline", "chronology", "phases", "era", "centuries", "1630 to", "evolution"]),
        ("M16", ["council", "ministers", "governance hub", "ashta pradhana", "mandala", "administration system", "cabinet", "hub"]),
        ("M19", ["forts", "fortress", "core of the state", "doctrine", "philosophy quote", "dark quote"]),
        ("M24", ["legacy", "summary", "before we move on", "takeaways", "conclusion", "what we learned"]),
        ("M21", ["three pillars", "justice", "trade and culture", "pillars", "cultural revival"]),
        ("M22", ["remarkable leaders", "women", "warrior queen", "dual biography", "two leaders", "tarabai", "ahilyabai"]),
        ("M14", ["wars", "rivalry", "anglo", "conflicts", "war periods", "three wars", "treaty"]),
        ("M06", ["navy", "naval", "ships", "fleet", "maritime force", "metrics navy"]),
        ("M20", ["coastal", "maritime supremacy", "masters of the coast", "naval battle"]),
        ("M17", ["revenue", "chauth", "sardeshmukhi", "coinage", "tax", "taxation", "kpi"]),
        ("M15", ["civilian administration", "administration", "coin", "gold coin", "hon"]),
        ("M07", ["guerrilla", "afzal khan", "military genius", "artefact", "did you know", "waghnakh"]),
        ("M08", ["bold campaigns", "night raid", "surat", "two campaigns", "strategy cards"]),
        ("M09", ["escape", "agra", "purandar", "daring", "story", "dramatic event"]),
        ("M10", ["coronation", "sovereignty", "conquest of south", "map", "territorial map"]),
        ("M11", ["visionary", "legend", "ethics", "moral", "insight panel"]),
        ("M12", ["resilience", "after shivaji", "painting", "successor", "sambhaji"]),
        ("M13", ["peshwas", "peshwa", "pan-indian", "expansion", "strip"]),
        ("M18", ["armed forces", "military administration", "weapons", "cavalry"]),
        ("M23", ["southern flowering", "thanjavur", "gallery", "culture focus", "art focus"]),
        ("M05", ["biography", "rise of", "foundation", "portrait"]),
        ("M03", ["origins", "who are", "origin story", "people"]),
    ]

    @classmethod
    def select(cls, slide_intent: str, slide_index: int = 1, used_layouts: Optional[List[str]] = None) -> str:
        """Select layout archetype code for given slide intent text."""
        clean = slide_intent.lower().strip()
        used = used_layouts or []

        for layout_code, keywords in cls.PATTERNS:
            for kw in keywords:
                if kw in clean:
                    return layout_code

        # Fallback: cycle through versatile narrative layouts to ensure variety
        narrative_cycle = ["M03", "M05", "M06", "M07", "M08", "M10", "M11", "M12", "M13", "M15", "M17", "M18", "M20"]
        for code in narrative_cycle:
            if code not in used[-3:]:
                return code

        return "M03"


class PresentationLayoutMemory:
    """Tracks layout usage across slides to ensure visual variety."""

    def __init__(self):
        self.used: List[str] = []
        self.dark_slide_count: int = 0

    def record(self, layout_code: str):
        self.used.append(layout_code)
        if layout_code in ("M01", "M19", "M24"):
            self.dark_slide_count += 1

    def suggest_avoiding(self) -> List[str]:
        """Returns recently used layouts that should be deprioritized."""
        return self.used[-3:] if len(self.used) >= 3 else self.used


class MarathaHeritageEditorialTheme:
    """DeckPilot AI Theme integration class for Maratha Heritage Editorial."""

    THEME_ID = THEME_ID
    THEME_NAME = THEME_NAME
    THEME_CATEGORY = THEME_CATEGORY

    # Map layout codes to layout builder functions
    LAYOUT_MAP: Dict[str, Any] = {
        "M01": layouts.render_m01_maroon_cover,
        "M02": layouts.render_m02_three_questions,
        "M03": layouts.render_m03_origin_glossary,
        "M04": layouts.render_m04_three_phase_timeline,
        "M05": layouts.render_m05_biography_glossary,
        "M06": layouts.render_m06_narrative_metrics_image,
        "M07": layouts.render_m07_artefact_didyouknow,
        "M08": layouts.render_m08_dual_campaign_cards,
        "M09": layouts.render_m09_story_centered_image,
        "M10": layouts.render_m10_narrative_map,
        "M11": layouts.render_m11_narrative_insight_panel,
        "M12": layouts.render_m12_narrative_painting,
        "M13": layouts.render_m13_narrative_strip,
        "M14": layouts.render_m14_three_periods_quote,
        "M15": layouts.render_m15_narrative_coin_insight,
        "M16": layouts.render_m16_governance_hub,
        "M17": layouts.render_m17_revenue_kpi_coin,
        "M18": layouts.render_m18_military_system,
        "M19": layouts.render_m19_dark_quote,
        "M20": layouts.render_m20_maritime_fact,
        "M21": layouts.render_m21_three_pillars_seal,
        "M22": layouts.render_m22_dual_leaders,
        "M23": layouts.render_m23_gallery_story,
        "M24": layouts.render_m24_dark_summary,
    }

    @classmethod
    def get_layout_function(cls, layout_code: str) -> Optional[Any]:
        return cls.LAYOUT_MAP.get(layout_code)

    @classmethod
    def select_layout(cls, slide_intent: str, slide_index: int = 1, used_layouts: Optional[List[str]] = None) -> str:
        return MarathaHeritageLayoutSelector.select(
            slide_intent=slide_intent,
            slide_index=slide_index,
            used_layouts=used_layouts
        )
