"""Icon Resolution and Responsive Sizing Engine for Rise of Empires Editorial Theme.

Provides authentic reference icons (from The Rise of Empires 3.pptx) and semantic
keyword mapping for empire, warfare, trade, diplomacy, archaeology, culture, and chronology.
"""

import os
import re
from typing import Dict, Optional, Tuple

ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")

# Semantic keyword to authentic icon file mapping
SEMANTIC_ICON_FILES: Dict[str, str] = {
    # Empire, Monarch & Central Authority
    "empire": "image-3-1.png",
    "emperor": "image-4-2.png",
    "ruler": "image-4-2.png",
    "king": "image-4-2.png",
    "monarch": "image-4-2.png",
    "sovereignty": "image-4-2.png",
    "throne": "image-8-1.png",
    "crown": "image-3-1.png",
    "dynasty": "image-9-1.png",
    "nanda": "image-9-1.png",
    "maurya": "image-12-1.png",
    "magadha": "image-8-1.png",
    # Warfare, Military & Expansion
    "army": "image-5-1.png",
    "military": "image-5-1.png",
    "war": "image-5-1.png",
    "warfare": "image-5-1.png",
    "battle": "image-11-1.png",
    "campaign": "image-11-1.png",
    "conquest": "image-5-1.png",
    "expansion": "image-5-1.png",
    "swords": "image-5-1.png",
    "conflict": "image-5-1.png",
    "kalinga": "image-16-1.png",
    "alexander": "image-10-1.png",
    "greece": "image-10-1.png",
    "greeks": "image-10-1.png",
    # Trade, Economy & Currency
    "trade": "image-6-1.png",
    "commerce": "image-6-1.png",
    "merchant": "image-6-1.png",
    "guild": "image-6-1.png",
    "shreni": "image-6-1.png",
    "route": "image-7-1.png",
    "routes": "image-7-1.png",
    "network": "image-7-1.png",
    "exchange": "image-6-1.png",
    "coin": "image-3-2.png",
    "currency": "image-3-2.png",
    "money": "image-3-2.png",
    "finance": "image-3-2.png",
    "economic": "image-6-1.png",
    # Law, Governance & Administration
    "administration": "image-4-1.png",
    "governance": "image-15-1.png",
    "government": "image-4-1.png",
    "law": "image-15-2.png",
    "justice": "image-15-2.png",
    "kautilya": "image-13-1.png",
    "chanakya": "image-13-1.png",
    "arthashastra": "image-13-1.png",
    "saptanga": "image-14-1.png",
    "strategy": "image-13-1.png",
    "welfare": "image-15-1.png",
    "people": "image-18-1.png",
    "society": "image-18-1.png",
    "daily": "image-18-1.png",
    "citizens": "image-18-1.png",
    # Philosophy, Peace & Edicts
    "peace": "image-16-1.png",
    "ashoka": "image-16-1.png",
    "dhamma": "image-16-1.png",
    "dharma": "image-16-1.png",
    "edict": "image-17-1.png",
    "edicts": "image-17-1.png",
    "inscription": "image-17-1.png",
    "stone": "image-17-1.png",
    "message": "image-17-1.png",
    "communication": "image-17-1.png",
    # Art, Architecture & Archaeology
    "art": "image-20-1.png",
    "terracotta": "image-20-1.png",
    "sculpture": "image-19-1.png",
    "architecture": "image-19-1.png",
    "stupa": "image-19-1.png",
    "pillar": "image-19-1.png",
    "capital": "image-19-1.png",
    "monument": "image-19-1.png",
    "artefact": "image-20-1.png",
    "museum": "image-20-1.png",
    "pottery": "image-18-1.png",
    "heritage": "image-23-1.png",
    "culture": "image-20-1.png",
    # Chronology, Decline & Legacy
    "timeline": "image-21-1.png",
    "chronology": "image-21-1.png",
    "era": "image-21-1.png",
    "history": "image-21-1.png",
    "decline": "image-22-1.png",
    "fall": "image-22-1.png",
    "fragile": "image-22-1.png",
    "causes": "image-22-1.png",
    "legacy": "image-23-1.png",
    "summary": "image-23-1.png",
    "conclusion": "image-23-1.png",
    "takeaway": "image-23-1.png",
    "questions": "image-2-1.png",
    "inquiry": "image-2-1.png",
    "overview": "image-4-1.png",
}

# Slide index to standard header icon
SLIDE_HEADER_ICONS: Dict[int, str] = {
    1: "image-1-2.png",
    2: "image-2-1.png",
    3: "image-3-1.png",
    4: "image-4-1.png",
    5: "image-5-1.png",
    6: "image-6-1.png",
    7: "image-7-1.png",
    8: "image-8-1.png",
    9: "image-9-1.png",
    10: "image-10-1.png",
    11: "image-11-1.png",
    12: "image-12-1.png",
    13: "image-13-1.png",
    14: "image-14-1.png",
    15: "image-15-1.png",
    16: "image-16-1.png",
    17: "image-17-1.png",
    18: "image-18-1.png",
    19: "image-19-1.png",
    20: "image-20-1.png",
    21: "image-21-1.png",
    22: "image-22-1.png",
    23: "image-23-1.png",
}


class IconResolver:
    """Resolves semantic icon keywords to verified PNG/SVG icon assets with fallbacks."""

    @classmethod
    def resolve_path(
        cls,
        semantic_hint: Optional[str] = None,
        slide_idx: Optional[int] = None,
        preferred_name: Optional[str] = None
    ) -> str:
        """Returns verified absolute filepath to icon asset. Never returns empty/invalid."""
        # 1. Preferred name check
        if preferred_name:
            cand = os.path.join(ICONS_DIR, preferred_name)
            if os.path.exists(cand):
                return cand
            cand_png = cand + ".png" if not preferred_name.endswith(".png") else cand
            if os.path.exists(cand_png):
                return cand_png

        # 2. Slide index lookup
        if slide_idx and slide_idx in SLIDE_HEADER_ICONS:
            fname = SLIDE_HEADER_ICONS[slide_idx]
            cand = os.path.join(ICONS_DIR, fname)
            if os.path.exists(cand):
                return cand

        # 3. Semantic keyword search
        if semantic_hint:
            clean = re.sub(r"[^a-zA-Z0-9\s]", " ", semantic_hint.lower())
            words = clean.split()
            for w in words:
                if w in SEMANTIC_ICON_FILES:
                    cand = os.path.join(ICONS_DIR, SEMANTIC_ICON_FILES[w])
                    if os.path.exists(cand):
                        return cand

        # 4. Fallback: default to image-4-1.png (features / gear emblem)
        default_file = os.path.join(ICONS_DIR, "image-4-1.png")
        if os.path.exists(default_file):
            return default_file

        # Fallback to any icon in the directory
        existing = [os.path.join(ICONS_DIR, f) for f in os.listdir(ICONS_DIR) if f.endswith(".png")]
        if existing:
            return existing[0]

        raise FileNotFoundError(f"No icon assets found in {ICONS_DIR}")

    @classmethod
    def calculate_badge_icon_geometry(
        cls,
        badge_x: float,
        badge_y: float,
        badge_diameter: float,
        glyph_ratio: float = 0.52
    ) -> Tuple[float, float, float, float]:
        """Calculates perfectly centered icon position within circular badge.

        Returns (icon_x, icon_y, icon_w, icon_h).
        """
        icon_dim = round(badge_diameter * glyph_ratio, 3)
        offset = round((badge_diameter - icon_dim) / 2.0, 3)
        icon_x = round(badge_x + offset, 3)
        icon_y = round(badge_y + offset, 3)
        return (icon_x, icon_y, icon_dim, icon_dim)
