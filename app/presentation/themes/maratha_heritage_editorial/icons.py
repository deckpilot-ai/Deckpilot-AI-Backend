"""Icon Resolution and Responsive Sizing Engine for Maratha Heritage Editorial Theme.

Provides authentic reference icons (from The Rise of the Marathas (4).pptx) and semantic
keyword mapping for historical, civilizational, military, naval, administrative, and cultural concepts.
"""

import os
import re
from typing import Dict, Optional, Tuple

ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")

# Semantic keyword to authentic icon file mapping
SEMANTIC_ICON_FILES: Dict[str, str] = {
    # Questions & Inquiry
    "questions": "image-2-1.png",
    "question": "image-2-1.png",
    "inquiry": "image-2-1.png",
    "puzzle": "image-2-1.png",
    "why": "image-2-1.png",
    "how": "image-2-1.png",

    # Origins, Geography & People
    "origins": "image-3-1.png",
    "origin": "image-3-1.png",
    "people": "image-3-1.png",
    "community": "image-3-1.png",
    "identity": "image-3-1.png",
    "geography": "image-3-1.png",
    "location": "image-10-1.png",
    "map": "image-10-1.png",
    "territory": "image-10-1.png",
    "expansion": "image-10-1.png",

    # Chronology & Timelines
    "timeline": "image-4-1.png",
    "chronology": "image-4-1.png",
    "history": "image-4-1.png",
    "era": "image-4-1.png",
    "period": "image-4-1.png",
    "centuries": "image-4-1.png",
    "evolution": "image-4-1.png",

    # Foundation, Sovereignty & Rulers
    "foundation": "image-5-1.png",
    "ruler": "image-5-1.png",
    "king": "image-5-1.png",
    "chhatrapati": "image-5-1.png",
    "leader": "image-5-1.png",
    "monarch": "image-5-1.png",
    "crown": "image-5-1.png",
    "coronation": "image-10-1.png",
    "sovereignty": "image-10-1.png",
    "swarajya": "image-5-3.png",
    "visionary": "image-11-1.png",
    "legend": "image-11-1.png",

    # Navy, Maritime & Coastal Supremacy
    "navy": "image-6-1.png",
    "maritime": "image-20-1.png",
    "naval": "image-6-1.png",
    "ship": "image-6-1.png",
    "ships": "image-20-1.png",
    "fleet": "image-6-1.png",
    "ocean": "image-20-1.png",
    "sea": "image-6-1.png",
    "coast": "image-20-1.png",
    "coastal": "image-20-1.png",
    "anchor": "image-6-1.png",

    # Military, Tactics & Campaigns
    "military": "image-18-1.png",
    "army": "image-18-1.png",
    "forces": "image-18-1.png",
    "weapon": "image-18-1.png",
    "weapons": "image-18-1.png",
    "sword": "image-18-1.png",
    "cavalry": "image-18-1.png",
    "infantry": "image-18-1.png",
    "battle": "image-8-2.png",
    "war": "image-14-1.png",
    "wars": "image-14-1.png",
    "campaign": "image-8-1.png",
    "campaigns": "image-8-1.png",
    "raid": "image-8-2.png",
    "guerrilla": "image-7-1.png",
    "tactics": "image-7-1.png",
    "strategy": "image-8-3.png",
    "escape": "image-9-1.png",
    "daring": "image-9-1.png",
    "resilience": "image-12-1.png",

    # Forts & Architecture
    "fort": "image-19-1.png",
    "forts": "image-19-1.png",
    "fortress": "image-19-1.png",
    "bastion": "image-19-1.png",
    "castle": "image-19-1.png",
    "architecture": "image-19-1.png",

    # Governance & Administration
    "governance": "image-15-1.png",
    "administration": "image-15-1.png",
    "council": "image-16-1.png",
    "ministers": "image-16-1.png",
    "mandala": "image-16-1.png",
    "peshwa": "image-13-1.png",
    "peshwas": "image-13-1.png",
    "prime_minister": "image-13-3.png",
    "civic": "image-15-1.png",
    "government": "image-15-1.png",

    # Economy, Revenue & Currency
    "revenue": "image-17-1.png",
    "coin": "image-17-1.png",
    "coins": "image-17-1.png",
    "coinage": "image-17-1.png",
    "tax": "image-17-1.png",
    "taxation": "image-17-1.png",
    "chauth": "image-17-1.png",
    "sardeshmukhi": "image-17-1.png",
    "finance": "image-17-1.png",
    "economy": "image-17-1.png",
    "trade": "image-21-3.png",
    "commerce": "image-21-3.png",

    # Justice, Law & Ethics
    "justice": "image-21-2.png",
    "law": "image-21-2.png",
    "courts": "image-21-2.png",
    "fairness": "image-21-2.png",
    "ethics": "image-11-2.png",
    "insight": "image-11-2.png",

    # Culture, Art & Heritage
    "culture": "image-21-4.png",
    "cultural": "image-21-4.png",
    "art": "image-23-1.png",
    "painting": "image-23-1.png",
    "literature": "image-23-1.png",
    "revival": "image-21-4.png",
    "seal": "image-21-4.png",
    "inscription": "image-23-1.png",
    "heritage": "image-24-1.png",
    "women": "image-22-1.png",
    "queen": "image-22-1.png",
    "leaders": "image-22-1.png",

    # Summary, Legacy & Takeaways
    "legacy": "image-24-1.png",
    "summary": "image-24-1.png",
    "conclusion": "image-24-1.png",
    "takeaways": "image-24-1.png",
    "check": "image-24-2.png",
    "quote": "image-19-2.png",
}

# Slide index to standard header icon
SLIDE_HEADER_ICONS: Dict[int, str] = {
    1: "image-5-1.png",     # Cover default (Ruler / Shivaji icon)
    2: "image-2-1.png",     # Questions
    3: "image-3-1.png",     # Origins
    4: "image-4-1.png",     # Chronology
    5: "image-5-1.png",     # Foundation
    6: "image-6-1.png",     # Navy
    7: "image-7-1.png",     # Military Genius
    8: "image-8-1.png",     # Bold Campaigns
    9: "image-9-1.png",     # Defeat & Daring
    10: "image-10-1.png",   # Sovereignty / Map
    11: "image-11-1.png",   # Visionary
    12: "image-12-1.png",   # Resilience
    13: "image-13-1.png",   # Governance Shifts
    14: "image-14-1.png",   # Final Rivalry
    15: "image-15-1.png",   # Governance
    16: "image-16-1.png",   # Council of Eight
    17: "image-17-1.png",   # Revenue & Coinage
    18: "image-18-1.png",   # Armed Forces
    19: "image-19-1.png",   # Forts
    20: "image-20-1.png",   # Masters of the Coast
    21: "image-21-1.png",   # Beyond the Battlefield
    22: "image-22-1.png",   # Remarkable Leaders
    23: "image-23-1.png",   # Southern Flowering
    24: "image-24-1.png",   # Before We Move On
}


class IconResolver:
    """Resolves semantic icon keywords to verified image files with optical centering."""

    @classmethod
    def resolve_path(cls, semantic_hint: Optional[str] = None, slide_index: Optional[int] = None) -> str:
        """Finds closest authentic icon asset path. NEVER returns missing/blank icon."""
        # 1. Semantic keyword lookup
        if semantic_hint:
            words = re.findall(r"[a-z0-9]+", str(semantic_hint).lower())
            for w in words:
                if w in SEMANTIC_ICON_FILES:
                    candidate = os.path.join(ICONS_DIR, SEMANTIC_ICON_FILES[w])
                    if os.path.exists(candidate):
                        return candidate

        # 2. Slide index lookup
        if slide_index and slide_index in SLIDE_HEADER_ICONS:
            candidate = os.path.join(ICONS_DIR, SLIDE_HEADER_ICONS[slide_index])
            if os.path.exists(candidate):
                return candidate

        # 3. Default fallback to general heritage / chronology icon
        default_file = os.path.join(ICONS_DIR, "image-4-1.png")
        if os.path.exists(default_file):
            return default_file

        # 4. Fallback to any icon available in directory
        if os.path.exists(ICONS_DIR):
            files = [f for f in os.listdir(ICONS_DIR) if f.endswith(".png")]
            if files:
                return os.path.join(ICONS_DIR, sorted(files)[0])

        raise FileNotFoundError(f"No valid icon assets found in {ICONS_DIR}")

    @classmethod
    def calculate_responsive_size(
        cls,
        badge_diameter_in: float,
        preferred_icon_ratio: float = 0.53,
        min_size_in: float = 0.28,
        max_size_in: float = 0.55
    ) -> float:
        """Calculates optical icon size relative to circular badge diameter."""
        size = badge_diameter_in * preferred_icon_ratio
        return max(min_size_in, min(max_size_in, round(size, 3)))

    @classmethod
    def calculate_optical_offset(
        cls,
        badge_x: float,
        badge_y: float,
        badge_diameter: float,
        icon_size: float
    ) -> Tuple[float, float]:
        """Calculates perfectly centered top-left coordinates for an icon inside a badge."""
        center_x = badge_x + (badge_diameter / 2.0)
        center_y = badge_y + (badge_diameter / 2.0)
        icon_x = round(center_x - (icon_size / 2.0), 3)
        icon_y = round(center_y - (icon_size / 2.0), 3)
        return (icon_x, icon_y)
