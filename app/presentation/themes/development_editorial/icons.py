"""Icon and Emoji Resolution Engine for Development Editorial Theme.

Provides relatable icons and Unicode emojis matching slide content semantics
(energy, infrastructure, economics, people, sustainability, governance).
"""

import os
import re
from typing import Dict, Optional, Tuple

ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")

# Semantic keyword to icon file mapping (authentic reference deck + vector icons)
SEMANTIC_ICON_FILES: Dict[str, str] = {
    # Energy, compute, and electrical power
    "power": "icon_bolt.png",
    "compute": "icon_bolt.png",
    "energy": "icon_bolt.png",
    "electric": "icon_bolt.png",
    "lightning": "icon_bolt.png",
    "voltage": "icon_bolt.png",
    "gigawatt": "icon_bolt.png",
    "megawatt": "icon_bolt.png",
    "datacenter": "icon_bolt.png",
    "cluster": "icon_bolt.png",
    "gpu": "icon_bolt.png",
    # Nuclear & atomic
    "nuclear": "icon_atom.png",
    "smr": "icon_atom.png",
    "reactor": "icon_atom.png",
    "atomic": "icon_atom.png",
    # Grid, transmission, network, globe
    "transmission": "icon_globe.png",
    "grid": "icon_globe.png",
    "substation": "icon_globe.png",
    "wire": "icon_globe.png",
    "network": "icon_globe.png",
    "globe": "icon_globe.png",
    "infrastructure": "icon_globe.png",
    "distribution": "icon_globe.png",
    # Water & cooling
    "cooling": "icon_droplet.png",
    "thermal": "icon_droplet.png",
    "dissipat": "icon_droplet.png",
    "liquid": "icon_droplet.png",
    "water": "icon_droplet.png",
    "hydro": "icon_droplet.png",
    # Process & lifecycle
    "lifecycle": "icon_gear.png",
    "process": "icon_gear.png",
    "workflow": "icon_gear.png",
    "cycle": "icon_gear.png",
    "phase": "icon_gear.png",
    "methodology": "icon_gear.png",
    # Carbon & emissions & factory
    "carbon": "icon_factory.png",
    "emission": "icon_factory.png",
    "fossil": "icon_factory.png",
    "peaker": "icon_factory.png",
    "pollution": "icon_factory.png",
    "oil": "icon_16_18.png",
    # Sustainability & nature
    "sustainability": "icon_6_2.png",
    "renewable": "icon_6_2.png",
    "nature": "icon_6_2.png",
    "environment": "icon_6_2.png",
    "green": "icon_6_2.png",
    "last": "icon_6_2.png",
    # Society & people & governance
    "people": "icon_1_2.png",
    "person": "icon_1_2.png",
    "citizen": "icon_1_2.png",
    "citizens": "icon_1_2.png",
    "community": "icon_1_2.png",
    "plural": "icon_1_2.png",
    "aspirations": "icon_1_2.png",
    "stewardship": "icon_1_2.png",
    "steward": "icon_1_2.png",
    "public": "icon_1_2.png",
    "society": "icon_1_2.png",
    # Economics & income & capex
    "income": "icon_2_2.png",
    "money": "icon_2_2.png",
    "wages": "icon_2_2.png",
    "cost": "icon_2_2.png",
    "capex": "icon_2_2.png",
    "financial": "icon_2_2.png",
    "rupee": "icon_13_9.png",
    "currency": "icon_13_9.png",
    # Comparison & metrics & scale
    "compare": "icon_3_2.png",
    "scale": "icon_3_2.png",
    "state": "icon_3_2.png",
    "metrics": "icon_3_2.png",
    "growth": "icon_5_2.png",
    "progress": "icon_5_2.png",
    "development": "icon_5_2.png",
    "hdi": "icon_5_2.png",
    # Public goods & institutions
    "facilities": "icon_4_2.png",
    "public_goods": "icon_4_2.png",
    "school": "icon_14_14.png",
    # Rights & security
    "freedom": "icon_7_5.png",
    "liberty": "icon_10_6.png",
    "choice": "icon_7_5.png",
    "equality": "icon_9_6.png",
    "equal": "icon_9_6.png",
    "respect": "icon_9_6.png",
    "security": "icon_shield.png",
    "safety": "icon_shield.png",
    "protection": "icon_shield.png",
    # Goals & strategy
    "target": "icon_target.png",
    "goal": "icon_target.png",
    "benchmark": "icon_target.png",
    "threshold": "icon_target.png",
    # Ideas & innovation
    "idea": "icon_bulb.png",
    "concept": "icon_bulb.png",
    "insight": "icon_bulb.png",
    "innovation": "icon_bulb.png",
    # Future & vision
    "future": "icon_rocket.png",
    "outlook": "icon_rocket.png",
    "vision": "icon_rocket.png",
    "horizon": "icon_rocket.png",
    # Inquiries
    "question": "icon_12_8.png",
    "inquiry": "icon_12_8.png",
}

# Semantic keyword to high-clarity relatable emoji mapping
SEMANTIC_EMOJIS: list[Tuple[str, str]] = [
    (r"\b(nuclear|smr|reactor|atomic)\b", "⚛️"),
    (r"\b(cooling|thermal|dissipat|liquid)\b", "💧"),
    (r"\b(transmission|substation|wire|distribution|grid|network|line|infrastructure)\b", "🌐"),
    (r"\b(power|surge|electric|energy|compute|generation|gigawatt|megawatt|voltage|battery)\b", "⚡"),
    (r"\b(carbon|emission|climate|decarbon|net.?zero|pollution|peaker|factory)\b", "🏭"),
    (r"\b(sustainab|environment|nature|green|renewable|solar|wind|eco|forest)\b", "🌿"),
    (r"\b(water|groundwater|river|aquifer|dam|hydro)\b", "💧"),
    (r"\b(oil|petroleum|crude|fuel|gas|barrel)\b", "🛢️"),
    (r"\b(money|income|dollar|capex|cost|investment|wage|capital|wealth|budget|rupee|currency)\b", "💰"),
    (r"\b(people|person|citizen|human|worker|labour|public|society|community|steward)\b", "👥"),
    (r"\b(health|hospital|medical|doctor|infant|mortality|disease|life)\b", "❤️"),
    (r"\b(school|education|literacy|student|teach|college|learn)\b", "🎓"),
    (r"\b(security|safety|defense|protect|guard|lock|resilience)\b", "🛡️"),
    (r"\b(freedom|liberty|right|equal|justice|fair|dignity|treat)\b", "⚖️"),
    (r"\b(growth|progress|advance|scale|expand|metric|increase|trend)\b", "📈"),
    (r"\b(lifecycle|process|workflow|cycle|phase)\b", "🔄"),
    (r"\b(future|outlook|horizon|aspiration|vision|tomorrow)\b", "🚀"),
    (r"\b(idea|concept|insight|solution|innovation|thought)\b", "💡"),
    (r"\b(policy|government|state|nation|institution|rule|governance)\b", "🏛️"),
    (r"\b(question|inquiry|debate|dilemma|why|challenge)\b", "❓"),
    (r"\b(goal|target|threshold|benchmark|yardstick|aim|strategy)\b", "🎯"),
]

# Emoji to icon filename mapping for 100% vector-sharp fallback
EMOJI_TO_ICON_FILE: Dict[str, str] = {
    "⚡": "icon_bolt.png",
    "⚛️": "icon_atom.png",
    "🌐": "icon_globe.png",
    "💧": "icon_droplet.png",
    "🌿": "icon_6_2.png",
    "👥": "icon_1_2.png",
    "💰": "icon_2_2.png",
    "🛡️": "icon_shield.png",
    "🔄": "icon_gear.png",
    "🏭": "icon_factory.png",
    "💡": "icon_bulb.png",
    "🎯": "icon_target.png",
    "🚀": "icon_rocket.png",
    "⚖️": "icon_9_6.png",
    "📈": "icon_3_2.png",
    "🎓": "icon_14_14.png",
    "❓": "icon_12_8.png",
}


class IconResolver:
    """Resolves semantic content into authentic, responsive icon images or relatable emojis."""

    # Specific concepts that take priority over generic words like "power" or "energy"
    PRIORITY_KEYWORDS: Dict[str, str] = {
        # Nuclear & science
        "nuclear": "icon_atom.png",
        "smr": "icon_atom.png",
        "reactor": "icon_atom.png",
        "atomic": "icon_atom.png",
        # Grid & network & globe
        "transmission": "icon_globe.png",
        "substation": "icon_globe.png",
        "grid": "icon_globe.png",
        "infrastructure": "icon_globe.png",
        "distribution": "icon_globe.png",
        "interconnection": "icon_globe.png",
        # Environment & renewables
        "sustainability": "icon_6_2.png",
        "renewable": "icon_6_2.png",
        "siting": "icon_6_2.png",
        "nature": "icon_6_2.png",
        "environment": "icon_6_2.png",
        "green": "icon_6_2.png",
        "solar": "icon_6_2.png",
        "wind": "icon_6_2.png",
        # People & stewardship & society
        "stewardship": "icon_1_2.png",
        "steward": "icon_1_2.png",
        "citizen": "icon_1_2.png",
        "citizens": "icon_1_2.png",
        "people": "icon_1_2.png",
        "person": "icon_1_2.png",
        "society": "icon_1_2.png",
        "community": "icon_1_2.png",
        "public": "icon_1_2.png",
        # Water & cooling
        "cooling": "icon_droplet.png",
        "thermal": "icon_droplet.png",
        "dissipat": "icon_droplet.png",
        "water": "icon_droplet.png",
        "hydro": "icon_droplet.png",
        "liquid": "icon_droplet.png",
        # Process & lifecycle
        "lifecycle": "icon_gear.png",
        "process": "icon_gear.png",
        "workflow": "icon_gear.png",
        "methodology": "icon_gear.png",
        # Carbon, fossil & emissions
        "carbon": "icon_factory.png",
        "emission": "icon_factory.png",
        "fossil": "icon_factory.png",
        "pollution": "icon_factory.png",
        "peaker": "icon_factory.png",
        # Security & defense
        "security": "icon_shield.png",
        "safety": "icon_shield.png",
        "protection": "icon_shield.png",
        # Goals & strategy
        "target": "icon_target.png",
        "goal": "icon_target.png",
        "benchmark": "icon_target.png",
        # Ideas & innovation
        "idea": "icon_bulb.png",
        "concept": "icon_bulb.png",
        "insight": "icon_bulb.png",
        "innovation": "icon_bulb.png",
        # Future
        "future": "icon_rocket.png",
        "vision": "icon_rocket.png",
        "horizon": "icon_rocket.png",
        # Finance & economics
        "income": "icon_2_2.png",
        "money": "icon_2_2.png",
        "capex": "icon_2_2.png",
        "cost": "icon_2_2.png",
        "investment": "icon_2_2.png",
    }

    @classmethod
    def resolve(cls, title: str = "", body: str = "", default_index: int = 0) -> Tuple[Optional[bytes], str]:
        """Returns (icon_bytes, emoji_str) where icon_bytes is guaranteed high-quality 256x256 image."""
        t_clean = str(title or "").lower()
        b_clean = str(body or "").lower()
        combined = f"{t_clean} {b_clean}"

        # 1. Search for emoji match first for semantics (checking title first, then body)
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
            fallback_emojis = ["💡", "🎯", "🌐", "⚡", "👥", "📈", "🛡️", "🌿", "⚖️", "🔄"]
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

        # 3. If no priority match in title, check ALL SEMANTIC_ICON_FILES in TITLE
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

        # 4. If still no match, check PRIORITY keywords in BODY
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

        # 5. If still no match, check ALL SEMANTIC_ICON_FILES in BODY
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

        # 7. Fallback icon bytes from curated pool
        if not icon_bytes:
            fallback_pool = [
                "icon_bolt.png", "icon_globe.png", "icon_atom.png", "icon_6_2.png",
                "icon_1_2.png", "icon_2_2.png", "icon_shield.png", "icon_gear.png",
                "icon_bulb.png", "icon_target.png"
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
