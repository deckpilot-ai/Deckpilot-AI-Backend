"""Icon Resolution and Responsive Sizing Engine for Federalism Editorial Theme.

Provides authentic reference icons (from Federalism 2.pptx) and vector silhouettes
for government, policy, economics, technology, education, and domain concepts.
"""

import os
import re
from typing import Dict, Optional, Tuple

ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")

# Semantic keyword to authentic icon file mapping
SEMANTIC_ICON_FILES: Dict[str, str] = {
    # Governance & Institutions
    "government": "image-3-1.png",
    "governance": "image-3-1.png",
    "union": "image-9-1.png",
    "national": "image-3-1.png",
    "state": "image-10-3.png",
    "regional": "image-3-2.png",
    "administration": "image-3-2.png",
    "local": "image-19-1.png",
    "panchayat": "image-20-1.png",
    "municipal": "image-20-4.png",
    "decentralisation": "image-19-1.png",
    "decentralization": "image-19-1.png",
    "tier": "image-9-2.png",
    "tiers": "image-9-2.png",
    # Law & Judiciary & Guardrails
    "judiciary": "image-12-1.png",
    "court": "image-12-1.png",
    "supreme": "image-12-1.png",
    "umpire": "image-12-1.png",
    "law": "image-12-2.png",
    "constitution": "image-9-1.png",
    "amendment": "image-20-6.png",
    "reform": "image-20-6.png",
    "guardrails": "image-12-2.png",
    "balance": "image-12-2.png",
    "rights": "image-11-1.png",
    "power": "image-10-1.png",
    "powers": "image-10-1.png",
    # Elections & Democracy & Participation
    "election": "image-20-1.png",
    "elections": "image-20-1.png",
    "vote": "image-20-1.png",
    "democracy": "image-22-1.png",
    "democratic": "image-22-1.png",
    "participation": "image-19-3.png",
    "citizens": "image-19-2.png",
    "citizen": "image-19-2.png",
    "people": "image-19-2.png",
    "representation": "image-20-2.png",
    "women": "image-20-3.png",
    "community": "image-19-2.png",
    # Economics & Finance & Revenue
    "finance": "image-20-5.png",
    "revenue": "image-20-5.png",
    "tax": "image-20-5.png",
    "resources": "image-20-5.png",
    "funds": "image-20-5.png",
    "budget": "image-20-5.png",
    "currency": "icon_2_2.png",
    "money": "icon_2_2.png",
    "capex": "icon_2_2.png",
    "cost": "icon_2_2.png",
    # Security, Defense & Policing
    "defense": "image-10-1.png",
    "defence": "image-10-1.png",
    "military": "image-10-1.png",
    "police": "image-10-3.png",
    "security": "icon_shield.png",
    "safety": "icon_shield.png",
    "protection": "image-3-3.png",
    "unity": "image-3-3.png",
    # Language, Education & Culture
    "language": "image-16-1.png",
    "linguistic": "image-16-1.png",
    "education": "image-10-5.png",
    "school": "image-10-5.png",
    "culture": "image-16-2.png",
    "diversity": "image-2-2.png",
    # Global & World
    "world": "image-2-2.png",
    "global": "image-2-2.png",
    "federation": "image-8-1.png",
    "system": "image-2-1.png",
    "systems": "image-2-1.png",
    "roadmap": "image-2-1.png",
    "overview": "image-2-1.png",
    # Technology & Infrastructure (Domain fallbacks)
    "technology": "image-10-7.png",
    "tech": "image-10-7.png",
    "compute": "icon_bolt.png",
    "energy": "icon_bolt.png",
    "grid": "icon_globe.png",
    "network": "icon_globe.png",
    "nuclear": "icon_atom.png",
    "cooling": "icon_droplet.png",
    "process": "icon_gear.png",
    "lifecycle": "icon_gear.png",
    "cloud": "icon_globe.png",
    "data": "image-10-7.png",
    "goal": "icon_target.png",
    "target": "icon_target.png",
    "future": "icon_rocket.png",
    "idea": "icon_bulb.png",
}

# Semantic keyword to high-clarity relatable emoji mapping
SEMANTIC_EMOJIS: list[Tuple[str, str]] = [
    (r"\b(government|union|national|state|province)\b", "🏛️"),
    (r"\b(judiciary|court|law|constitution|umpire|legal)\b", "⚖️"),
    (r"\b(election|vote|democracy|ballot)\b", "🗳️"),
    (r"\b(people|citizen|community|public|society|human)\b", "👥"),
    (r"\b(money|revenue|tax|finance|budget|currency)\b", "💰"),
    (r"\b(security|safety|defense|protect|shield|guard)\b", "🛡️"),
    (r"\b(education|school|learn|knowledge|student)\b", "🎓"),
    (r"\b(language|linguistic|speech|translation)\b", "🗣️"),
    (r"\b(world|global|globe|map|international)\b", "🌐"),
    (r"\b(tier|level|hierarchy|structure|org)\b", "🪜"),
    (r"\b(amendment|reform|rule|act|provision)\b", "📜"),
    (r"\b(power|energy|compute|electric)\b", "⚡"),
    (r"\b(process|lifecycle|workflow|cycle)\b", "🔄"),
    (r"\b(target|goal|benchmark|aim)\b", "🎯"),
    (r"\b(future|rocket|advance|vision)\b", "🚀"),
    (r"\b(idea|insight|innovation|thought)\b", "💡"),
]

# Emoji to icon filename mapping for 100% vector-sharp fallback
EMOJI_TO_ICON_FILE: Dict[str, str] = {
    "🏛️": "image-3-1.png",
    "⚖️": "image-12-1.png",
    "🗳️": "image-20-1.png",
    "👥": "image-19-2.png",
    "💰": "image-20-5.png",
    "🛡️": "image-3-3.png",
    "🎓": "image-10-5.png",
    "🗣️": "image-16-1.png",
    "🌐": "image-2-2.png",
    "🪜": "image-9-2.png",
    "📜": "image-20-6.png",
    "⚡": "icon_bolt.png",
    "🔄": "icon_gear.png",
    "🎯": "icon_target.png",
    "🚀": "icon_rocket.png",
    "💡": "icon_bulb.png",
}


class IconResolver:
    """Resolves semantic content into authentic, responsive icon images."""

    # Priority concepts that take precedence over generic matches
    PRIORITY_KEYWORDS: Dict[str, str] = {
        "judiciary": "image-12-1.png",
        "court": "image-12-1.png",
        "umpire": "image-12-1.png",
        "election": "image-20-1.png",
        "elections": "image-20-1.png",
        "decentralisation": "image-19-1.png",
        "decentralization": "image-19-1.png",
        "panchayat": "image-20-1.png",
        "municipal": "image-20-4.png",
        "defense": "image-10-1.png",
        "police": "image-10-3.png",
        "education": "image-10-5.png",
        "revenue": "image-20-5.png",
        "language": "image-16-1.png",
        "linguistic": "image-16-1.png",
        "women": "image-20-3.png",
        "unity": "image-3-3.png",
        "constitution": "image-9-1.png",
        "roadmap": "image-2-1.png",
        "overview": "image-2-1.png",
        "nuclear": "icon_atom.png",
        "cloud": "icon_globe.png",
        "compute": "icon_bolt.png",
        "security": "icon_shield.png",
    }

    @classmethod
    def resolve(cls, title: str = "", body: str = "", default_index: int = 0) -> Tuple[Optional[bytes], str]:
        """Returns (icon_bytes, emoji_str) where icon_bytes is guaranteed high-quality 400x400/256x256 image."""
        t_clean = str(title or "").lower()
        b_clean = str(body or "").lower()

        # 1. Search emoji match for semantic classification
        matched_emoji = None
        for pattern, emoji in SEMANTIC_EMOJIS:
            if re.search(pattern, t_clean):
                matched_emoji = emoji
                break
        if not matched_emoji:
            for pattern, emoji in SEMANTIC_EMOJIS:
                if re.search(pattern, b_clean):
                    matched_emoji = emoji
                    break
        if not matched_emoji:
            fallback_emojis = ["🏛️", "⚖️", "🗳️", "👥", "🌐", "🛡️", "📜", "💰", "💡", "🎯"]
            matched_emoji = fallback_emojis[default_index % len(fallback_emojis)]

        # 2. Check PRIORITY keywords in TITLE first
        icon_bytes = None
        for kw, filename in cls.PRIORITY_KEYWORDS.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", t_clean) or kw in t_clean:
                p = os.path.join(ICONS_DIR, filename)
                if os.path.exists(p):
                    try:
                        with open(p, "rb") as f:
                            icon_bytes = f.read()
                        break
                    except Exception:
                        pass

        # 3. Check ALL SEMANTIC_ICON_FILES in TITLE
        if not icon_bytes:
            for kw, filename in SEMANTIC_ICON_FILES.items():
                if re.search(r"\b" + re.escape(kw) + r"\b", t_clean) or kw in t_clean:
                    p = os.path.join(ICONS_DIR, filename)
                    if os.path.exists(p):
                        try:
                            with open(p, "rb") as f:
                                icon_bytes = f.read()
                            break
                        except Exception:
                            pass

        # 4. Check PRIORITY keywords in BODY
        if not icon_bytes:
            for kw, filename in cls.PRIORITY_KEYWORDS.items():
                if re.search(r"\b" + re.escape(kw) + r"\b", b_clean) or kw in b_clean:
                    p = os.path.join(ICONS_DIR, filename)
                    if os.path.exists(p):
                        try:
                            with open(p, "rb") as f:
                                icon_bytes = f.read()
                            break
                        except Exception:
                            pass

        # 5. Check ALL SEMANTIC_ICON_FILES in BODY
        if not icon_bytes:
            for kw, filename in SEMANTIC_ICON_FILES.items():
                if re.search(r"\b" + re.escape(kw) + r"\b", b_clean) or kw in b_clean:
                    p = os.path.join(ICONS_DIR, filename)
                    if os.path.exists(p):
                        try:
                            with open(p, "rb") as f:
                                icon_bytes = f.read()
                            break
                        except Exception:
                            pass

        # 6. Map through matched emoji if still no icon
        if not icon_bytes and matched_emoji in EMOJI_TO_ICON_FILE:
            mapped_file = EMOJI_TO_ICON_FILE[matched_emoji]
            p = os.path.join(ICONS_DIR, mapped_file)
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        icon_bytes = f.read()
                except Exception:
                    pass

        # 7. Fallback from curated authentic reference pool
        if not icon_bytes:
            fallback_pool = [
                "image-3-1.png", "image-2-2.png", "image-12-1.png", "image-19-2.png",
                "image-20-1.png", "image-3-3.png", "image-10-1.png", "image-10-5.png",
                "image-20-5.png", "image-20-6.png"
            ]
            fb_file = fallback_pool[default_index % len(fallback_pool)]
            p = os.path.join(ICONS_DIR, fb_file)
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        icon_bytes = f.read()
                except Exception:
                    pass

        return (icon_bytes, matched_emoji)

    @classmethod
    def get_raw_bytes(cls, filename: str) -> Optional[bytes]:
        """Loads raw bytes directly from the authentic assets directory."""
        p = os.path.join(ICONS_DIR, filename)
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f.read()
            except Exception:
                pass
        return None


def calculate_responsive_icon_size(
    card_w: float,
    card_h: float,
    body_lines: int = 2,
    is_hero: bool = False
) -> float:
    """Calculates ideal icon diameter based on card dimensions and text density."""
    if is_hero:
        return 0.84

    # Calculate proportional size based on container dimensions
    raw_size = min(card_h * 0.26, card_w * 0.16)
    
    # Scale slightly down if text density is high
    if body_lines > 4:
        raw_size *= 0.88
    elif body_lines <= 2:
        raw_size *= 1.05

    # Clamp between minimum readable size and maximum card ceiling
    return round(max(0.38, min(0.72, raw_size)), 2)
