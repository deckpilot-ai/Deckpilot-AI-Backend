"""Theme Registry and Semantic Layout Selector for Rise of Empires Editorial Theme.

Registers the `rise-of-empires-editorial-v1` theme with DeckPilot AI's theme registry
and provides a historical layout selector with presentation memory.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.presentation.themes.rise_of_empires_editorial.tokens import COLORS, GEOMETRY, FONTS
from app.presentation.themes.rise_of_empires_editorial import layouts

logger = logging.getLogger(__name__)

THEME_ID = "rise-of-empires-editorial-v1"
THEME_NAME = "Rise of Empires Editorial"
THEME_CATEGORY = "heritage-editorial"


class HistoricalEditorialLayoutSelector:
    """Selects the optimal layout archetype for a slide based on semantic intent.

    Priority signals:
    - presence of chronology / timeline keywords → E21
    - presence of dominant map → E07 / E12
    - presence of 7-part / framework → E14
    - presence of philosophy / quote / wisdom → E15
    - presence of museum artefacts gallery → E20
    - presence of hub & spoke / features list → E04
    - big questions (intro slide) → E02
    - biography → E13
    - causes / decline → E22
    - dark summary / legacy → E23
    - dark cover → E01
    - remaining → default parchment layouts E03, E06, E08-E12, E16-E19
    """

    # Pattern registry: ordered by specificity
    PATTERNS: List[Tuple[str, List[str]]] = [
        ("E01", ["cover", "title slide", "introduction", "opening"]),
        ("E02", ["big questions", "questions", "inquiry", "setting the scene", "objectives"]),
        ("E04", ["hub", "features of", "limbs of", "elements of", "components of", "spokes"]),
        ("E14", ["seven", "saptanga", "seven limbs", "framework", "seven pillars", "seven parts"]),
        ("E15", ["quote", "philosophy", "wisdom", "welfare of", "in the happiness", "moral"]),
        ("E21", ["timeline", "chronology", "600 to", "bce timeline", "era timeline", "centuries timeline"]),
        ("E20", ["gallery", "terracotta", "museum", "artefacts", "clay", "sculptures", "art gallery"]),
        ("E22", ["causes", "fall", "decline", "fragile", "collapse", "why empires fall"]),
        ("E23", ["legacy", "summary", "before we move on", "what we learned", "conclusion", "takeaways"]),
        ("E13", ["biography", "story of", "life of", "strategist", "adviser", "philosopher"]),
        ("E07", ["trade route", "routes", "map of trade", "great routes", "networks of exchange"]),
        ("E12", ["empire map", "empire at its peak", "territory", "extent of", "mauryan empire"]),
        ("E06", ["trade", "economy", "guild", "commerce", "shreni", "economic"]),
        ("E08", ["magadha", "rise of", "first empire", "origin", "rise begins"]),
        ("E09", ["dynasty", "nanda", "king", "first dynasty"]),
        ("E10", ["greeks", "alexander", "arrival", "power from the west", "campaign"]),
        ("E11", ["eastern campaign", "india campaign", "in india", "indus"]),
        ("E16", ["kalinga", "war", "battle", "chose peace", "edict", "ashoka and"]),
        ("E17", ["carved in stone", "inscriptions", "communicator", "messages", "edicts of"]),
        ("E18", ["everyday life", "daily life", "mauryan period", "life in"]),
        ("E19", ["art and architecture", "achievements", "enduring", "monuments", "pillars"]),
        ("E05", ["why", "how", "kingdom to empire", "expansion", "expanded"]),
        ("E03", ["what is", "definition", "core idea", "meaning of", "concept"]),
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

        # Fallback: cycle through body layouts to ensure variety
        body_cycle = ["E06", "E08", "E09", "E10", "E11", "E16", "E17", "E18", "E19", "E03"]
        for code in body_cycle:
            if code not in used[-3:]:
                return code

        return "E06"


class PresentationLayoutMemory:
    """Tracks layout usage across slides to ensure visual variety."""

    def __init__(self):
        self.used: List[str] = []
        self.dark_slide_count: int = 0

    def record(self, layout_code: str):
        self.used.append(layout_code)
        if layout_code in ("E01", "E15", "E23"):
            self.dark_slide_count += 1

    def suggest_avoiding(self) -> List[str]:
        """Returns recently used layouts that should be deprioritized."""
        return self.used[-3:] if len(self.used) >= 3 else self.used


class RiseOfEmpiresEditorialTheme:
    """DeckPilot AI Theme integration class for Rise of Empires Editorial."""

    THEME_ID = THEME_ID
    THEME_NAME = THEME_NAME
    THEME_CATEGORY = THEME_CATEGORY

    # Map layout codes to layout builder functions
    LAYOUT_MAP: Dict[str, Any] = {
        "E01": layouts.render_e01_dark_cover,
        "E02": layouts.render_e02_big_questions,
        "E03": layouts.render_e03_explanation_image_glossary,
        "E04": layouts.render_e04_hub_six_features,
        "E05": layouts.render_e05_why_how_gallery,
        "E06": layouts.render_e06_explanation_hero_glossary,
        "E07": layouts.render_e07_map_explanation,
        "E08": layouts.render_e08_explanation_image_insight,
        "E09": layouts.render_e09_narrative_artefact_map,
        "E10": layouts.render_e10_narrative_multiple_maps,
        "E11": layouts.render_e11_body_artefact_did_you_know,
        "E12": layouts.render_e12_body_dominant_map,
        "E13": layouts.render_e13_biography_painting_definition,
        "E14": layouts.render_e14_seven_part_framework,
        "E15": layouts.render_e15_dark_quote,
        "E16": layouts.render_e16_event_image_glossary,
        "E17": layouts.render_e17_body_map_document,
        "E18": layouts.render_e18_daily_life_artefact,
        "E19": layouts.render_e19_hero_artefact_showcase,
        "E20": layouts.render_e20_museum_gallery,
        "E21": layouts.render_e21_historical_timeline,
        "E22": layouts.render_e22_causes_interpretation,
        "E23": layouts.render_e23_dark_summary,
    }

    @classmethod
    def get_layout_function(cls, layout_code: str) -> Optional[Any]:
        return cls.LAYOUT_MAP.get(layout_code)

    @classmethod
    def select_layout(cls, slide_intent: str, slide_index: int = 1, used_layouts: Optional[List[str]] = None) -> str:
        return HistoricalEditorialLayoutSelector.select(
            slide_intent=slide_intent,
            slide_index=slide_index,
            used_layouts=used_layouts
        )
