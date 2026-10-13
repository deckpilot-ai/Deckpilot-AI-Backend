"""DeckPilot Theme Engine: Domain classification, 14 WCAG contrast palettes, and contrast guarantees.

Ported and enhanced from deckpilot-skill for enterprise production use.
Ensures mathematical WCAG AA contrast guarantees across light, dark, and sandwich surface modes.
"""

from __future__ import annotations

import colorsys
import re
from typing import Any

from app.schemas.generation_state import (
    ColorPalette,
    DesignSystem,
    FontConfig,
    TypographyHierarchy,
)

# ── 14 Curated Palettes from deckpilot-skill ──────────────────────────────
PALETTES: dict[str, dict[str, Any]] = {
    "finance": {
        "name": "Midnight Executive",
        "primary": "1E2761",
        "secondary": "CADCFC",
        "accent": "F2A900",
        "mode": "sandwich",
        "fonts": ["Cambria", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.08,
    },
    "tech": {
        "name": "Deep Indigo",
        "primary": "0F172A",
        "secondary": "818CF8",
        "accent": "22D3EE",
        "mode": "dark",
        "fonts": ["Segoe UI", "Segoe UI"],
        "motif": "numbered-badges",
        "radius": 0.12,
    },
    "health": {
        "name": "Teal Trust",
        "primary": "028090",
        "secondary": "00A896",
        "accent": "E4572E",
        "mode": "light",
        "fonts": ["Calibri", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.15,
    },
    "wellness": {
        "name": "Sage Calm",
        "primary": "50808E",
        "secondary": "84B59F",
        "accent": "E9A820",
        "mode": "light",
        "fonts": ["Cambria", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.20,
    },
    "education": {
        "name": "Playful Navy",
        "primary": "2F3C7E",
        "secondary": "F9E795",
        "accent": "F96167",
        "mode": "light",
        "fonts": ["Calibri", "Calibri"],
        "motif": "numbered-badges",
        "radius": 0.20,
    },
    "agri_env": {
        "name": "Forest & Moss",
        "primary": "2C5F2D",
        "secondary": "97BC62",
        "accent": "E9A820",
        "mode": "sandwich",
        "fonts": ["Cambria", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.10,
    },
    "energy": {
        "name": "Charcoal Signal",
        "primary": "36454F",
        "secondary": "CBD5DB",
        "accent": "FF6B00",
        "mode": "sandwich",
        "fonts": ["Arial", "Arial"],
        "motif": "numbered-badges",
        "radius": 0.08,
    },
    "food": {
        "name": "Warm Terracotta",
        "primary": "B85042",
        "secondary": "A7BEAE",
        "accent": "E7C873",
        "mode": "light",
        "fonts": ["Bookman Old Style", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.15,
    },
    "creative": {
        "name": "Coral Energy",
        "primary": "F96167",
        "secondary": "F9E795",
        "accent": "2F3C7E",
        "mode": "sandwich",
        "fonts": ["Calibri", "Calibri"],
        "motif": "numbered-badges",
        "radius": 0.20,
    },
    "science": {
        "name": "Ocean Gradient",
        "primary": "21295C",
        "secondary": "1C7293",
        "accent": "7DD3FC",
        "mode": "dark",
        "fonts": ["Cambria", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.08,
    },
    "luxury": {
        "name": "Noir Gold",
        "primary": "111111",
        "secondary": "D9D9D9",
        "accent": "C9A227",
        "mode": "dark",
        "fonts": ["Bookman Old Style", "Calibri"],
        "motif": "numbered-badges",
        "radius": 0.05,
    },
    "sports": {
        "name": "Cherry Bold",
        "primary": "990011",
        "secondary": "FCF6F5",
        "accent": "2F3C7E",
        "mode": "sandwich",
        "fonts": ["Arial", "Arial"],
        "motif": "numbered-badges",
        "radius": 0.05,
    },
    "legal_gov": {
        "name": "Slate Authority",
        "primary": "1F2937",
        "secondary": "E5E7EB",
        "accent": "9A7B2F",
        "mode": "sandwich",
        "fonts": ["Century Schoolbook", "Arial"],
        "motif": "icons-in-circles",
        "radius": 0.06,
    },
    "fashion": {
        "name": "Berry & Rose",
        "primary": "6D2E46",
        "secondary": "A26769",
        "accent": "D4A373",
        "mode": "sandwich",
        "fonts": ["Bookman Old Style", "Calibri"],
        "motif": "icons-in-circles",
        "radius": 0.20,
    },
}

# ── Domain Classification Keywords ───────────────────────────────────────
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "finance": [
        "bank", "banking", "investment", "investor", "revenue", "budget", "audit",
        "consulting", "strategy", "quarterly", "financial", "finance", "profit",
        "board", "m&a", "fund", "insurance", "enrollment", "claims", "ebitda", "arr", "mrr", "valuation", "fiscal",
    ],
    "tech": [
        "ai", "artificial intelligence", "software", "cloud", "cyber", "security",
        "data", "api", "platform", "machine learning", "llm", "devops", "saas",
        "blockchain", "architecture", "agent", "kubernetes", "infra", "infrastructure", "latency",
    ],
    "health": [
        "patient", "clinical", "hospital", "medical", "pharma", "healthcare",
        "disease", "doctor", "nursing", "therapy", "diagnosis", "public health", "biotech",
    ],
    "wellness": [
        "wellness", "mental health", "mindfulness", "yoga", "nutrition", "fitness",
        "meditation", "self-care", "sleep",
    ],
    "education": [
        "student", "school", "lesson", "curriculum", "training", "learning", "course",
        "teacher", "classroom", "ncert", "cbse", "syllabus", "university", "exam", "textbook", "grade",
    ],
    "agri_env": [
        "farm", "farming", "crop", "agriculture", "climate", "forest", "sustainab",
        "soil", "water", "ecology", "environment", "wildlife", "biodiversity",
        "irrigation", "geography", "ocean", "river", "development",
    ],
    "energy": [
        "oil", "gas", "solar", "grid", "manufactur", "construction", "engineering",
        "industrial", "mining", "utility", "power plant", "logistics", "supply chain", "automotive",
    ],
    "food": [
        "restaurant", "recipe", "hotel", "travel", "tourism", "menu", "cuisine",
        "hospitality", "cafe", "catering", "food",
    ],
    "creative": [
        "brand", "campaign", "marketing", "design", "pitch", "launch",
        "social media", "advertising", "product launch", "creative", "portfolio",
    ],
    "science": [
        "research", "physics", "space", "astronomy", "chemistry", "lab",
        "experiment", "biology", "quantum", "scientific", "universe", "planet",
    ],
    "luxury": [
        "luxury", "real estate", "premium", "jewel", "property", "yacht", "watch",
    ],
    "sports": [
        "sport", "football", "cricket", "athlete", "tournament", "league", "olympic", "match",
    ],
    "legal_gov": [
        "policy", "law", "legal", "compliance", "government", "regulation",
        "public sector", "legislation", "court", "governance", "ministry",
        "federal", "federalism", "empire", "maratha", "constitution", "history", "sovereign",
    ],
    "fashion": [
        "fashion", "beauty", "cosmetic", "apparel", "runway", "boutique", "style", "textile", "cotton",
    ],
}


# ── Color Math & WCAG Contrast Guarantee Functions ─────────────────────────
def clean_hex(h: str) -> str:
    cleaned = str(h).strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", cleaned):
        # Fallback to default navy if invalid
        return "1E2761"
    return cleaned


def to_rgb(h: str) -> tuple[int, int, int]:
    cleaned = clean_hex(h)
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def to_hex(rgb: tuple[float, float, float] | tuple[int, int, int]) -> str:
    return "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """Linearly interpolate colors: t=0 -> a, t=1 -> b."""
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex((ra[0] * (1.0 - t) + rb[0] * t, ra[1] * (1.0 - t) + rb[1] * t, ra[2] * (1.0 - t) + rb[2] * t))


def _lin(c: float) -> float:
    c_norm = c / 255.0
    return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4


def luminance(h: str) -> float:
    """Calculates relative luminance of sRGB color per WCAG 2.1."""
    r, g, b = to_rgb(h)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Calculates WCAG 2.1 contrast ratio between foreground and background."""
    l1, l2 = sorted([luminance(fg), luminance(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _hls(h: str) -> tuple[float, float, float]:
    r, g, b = (c / 255.0 for c in to_rgb(h))
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(hh: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(hh, max(0.0, min(1.0, l)), s)
    return to_hex((r * 255.0, g * 255.0, b * 255.0))


def ensure_contrast(fg: str, bg: str, minimum: float = 4.5) -> str:
    """Adjusts lightness of fg until contrast ratio against bg >= minimum."""
    if contrast_ratio(fg, bg) >= minimum:
        return clean_hex(fg)
    hh, l, s = _hls(fg)
    step = 0.02 if luminance(bg) < 0.5 else -0.02
    for _ in range(60):
        l += step
        cand = _from_hls(hh, l, s)
        if contrast_ratio(cand, bg) >= minimum:
            return cand
        if l <= 0.0 or l >= 1.0:
            break
    return "FFFFFF" if luminance(bg) < 0.5 else "111111"


def best_text(bg: str, light: str = "FFFFFF", dark: str = "1F2937") -> str:
    """Picks either light or dark text that offers superior contrast on bg."""
    return light if contrast_ratio(light, bg) >= contrast_ratio(dark, bg) else dark


def darken_to(h: str, max_l: float) -> str:
    hh, l, s = _hls(h)
    return _from_hls(hh, min(l, max_l), s) if l > max_l else clean_hex(h)


# ── Domain Classification ──────────────────────────────────────────────────
def classify_domain(text: str) -> tuple[str, dict[str, float]]:
    """Classifies topic semantics to the closest matching domain palette."""
    t = " " + re.sub(r"[^a-z0-9&+ ]", " ", text.lower()) + " "
    scores: dict[str, float] = {}
    for dom, words in DOMAIN_KEYWORDS.items():
        sc = 0.0
        for w in words:
            pat = f" {w} " if len(w) <= 3 else w
            if pat in t:
                sc += 1.0 + (1.0 if len(w) > 6 else 0.0)
        scores[dom] = sc
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0.0:
        return "finance", scores
    return best, scores


# ── Theme Generation ──────────────────────────────────────────────────────
def build_theme(
    subject: str = "",
    brand_color: str | None = None,
    mode: str | None = None,
    palette_key: str | None = None,
) -> dict[str, Any]:
    """Generates a complete, contrast-safe presentation theme for any subject or brand."""
    domain, _scores = classify_domain(subject)
    key = palette_key if palette_key in PALETTES else domain
    p = dict(PALETTES.get(key, PALETTES["finance"]))

    if brand_color:
        cleaned_b = clean_hex(brand_color)
        p["primary"] = cleaned_b
        p["name"] = f"Brand ({cleaned_b})"
    if mode in ("light", "dark", "sandwich"):
        p["mode"] = mode

    primary = clean_hex(p["primary"])
    secondary = clean_hex(p["secondary"])
    accent = clean_hex(p["accent"])
    white = "FFFFFF"

    # Light surface (for standard body slides)
    ink = ensure_contrast(primary, white, 7.0)
    text = ensure_contrast(mix("1F2937", primary, 0.12), white, 10.0)
    muted = ensure_contrast("6B7280", white, 4.6)
    card_l = mix(white, primary, 0.06)
    acc_l = ensure_contrast(ensure_contrast(accent, white, 3.0), card_l, 3.0)

    light_surface = {
        "bg": white,
        "heading": ink,
        "text": text,
        "muted": muted,
        "card": card_l,
        "cardText": text,
        "accent": acc_l,
        "iconBg": ink,
        "iconFg": best_text(ink),
        "hero": ink,
        "heroText": best_text(ink),
        "line": mix(white, primary, 0.20),
        "series": [ink, acc_l, mix(ink, white, 0.45), mix(acc_l, ink, 0.50), muted],
    }

    # Dark surface (for hero, title, divider, and closing slides)
    bg_dark = darken_to(primary, 0.16) if luminance(primary) > 0.05 else primary
    d_accent = ensure_contrast(accent, bg_dark, 4.5)
    d_secondary = ensure_contrast(secondary, bg_dark, 4.5)
    d_card = mix(bg_dark, white, 0.08)

    dark_surface = {
        "bg": bg_dark,
        "heading": white,
        "text": "F3F4F6",
        "muted": ensure_contrast(mix(white, bg_dark, 0.4), bg_dark, 4.6),
        "card": d_card,
        "cardText": white,
        "accent": d_accent,
        "iconBg": d_accent,
        "iconFg": best_text(d_accent, light="FFFFFF", dark=bg_dark),
        "hero": mix(bg_dark, white, 0.14),
        "heroText": white,
        "line": mix(bg_dark, white, 0.20),
        "secondary": d_secondary,
        "series": [d_accent, d_secondary, mix(d_accent, bg_dark, 0.45), mix(d_secondary, bg_dark, 0.50), "9CA3AF"],
    }

    fonts = p.get("fonts", ["Cambria", "Calibri"])
    return {
        "name": p["name"],
        "domain": key,
        "mode": p["mode"],
        "fonts": {"heading": fonts[0], "body": fonts[1]},
        "motif": p.get("motif", "icons-in-circles"),
        "radius": p.get("radius", 0.08),
        "raw": {"primary": primary, "secondary": secondary, "accent": accent},
        "light": light_surface,
        "dark": dark_surface,
    }


def audit_theme(theme: dict[str, Any]) -> list[dict[str, Any]]:
    """Audits theme contrast against WCAG AA standards. Returns list of defects (empty = perfect)."""
    problems: list[dict[str, Any]] = []
    pairs = [
        ("light", "heading/bg", theme["light"]["heading"], theme["light"]["bg"], 4.5),
        ("light", "text/bg", theme["light"]["text"], theme["light"]["bg"], 4.5),
        ("light", "muted/bg", theme["light"]["muted"], theme["light"]["bg"], 4.5),
        ("light", "cardText/card", theme["light"]["cardText"], theme["light"]["card"], 4.5),
        ("light", "heroText/hero", theme["light"]["heroText"], theme["light"]["hero"], 4.5),
        ("light", "iconFg/iconBg", theme["light"]["iconFg"], theme["light"]["iconBg"], 3.0),
        ("light", "accent/bg", theme["light"]["accent"], theme["light"]["bg"], 3.0),
        ("light", "accent/card", theme["light"]["accent"], theme["light"]["card"], 3.0),
        ("dark", "heading/bg", theme["dark"]["heading"], theme["dark"]["bg"], 4.5),
        ("dark", "text/bg", theme["dark"]["text"], theme["dark"]["bg"], 4.5),
        ("dark", "muted/bg", theme["dark"]["muted"], theme["dark"]["bg"], 4.5),
        ("dark", "cardText/card", theme["dark"]["cardText"], theme["dark"]["card"], 4.5),
        ("dark", "heroText/hero", theme["dark"]["heroText"], theme["dark"]["hero"], 4.5),
        ("dark", "iconFg/iconBg", theme["dark"]["iconFg"], theme["dark"]["iconBg"], 3.0),
        ("dark", "accent/bg", theme["dark"]["accent"], theme["dark"]["bg"], 3.0),
    ]
    for surf, name, fg, bg, need in pairs:
        r = contrast_ratio(fg, bg)
        if r < need:
            problems.append({"surface": surf, "pair": name, "ratio": round(r, 2), "need": need})
    return problems


def theme_to_design_system(theme: dict[str, Any]) -> DesignSystem:
    """Converts a theme dict into the strongly-typed DesignSystem schema model."""
    light = theme["light"]
    dark = theme["dark"]

    palette = ColorPalette(
        ink=f"#{light['heading']}",
        primary=f"#{theme['raw']['primary']}",
        secondary=f"#{theme['raw']['secondary']}",
        accent=f"#{light['accent']}",
        tint_a=f"#{light['card']}",
        tint_b=f"#{mix('FFFFFF', theme['raw']['primary'], 0.12)}",
        alert="#C63A28",
        neutral=f"#{light['card']}",
        background=f"#{light['bg']}",
        paper=f"#{light['card']}",
        card_fill=f"#{light['card']}",
        text_primary=f"#{light['text']}",
        text_secondary=f"#{light['muted']}",
        text_on_dark=f"#{dark['heading']}",
        chart_colors=[f"#{c}" for c in light["series"]],
    )

    h_font = theme["fonts"]["heading"]
    b_font = theme["fonts"]["body"]

    typography = TypographyHierarchy(
        title_font=FontConfig(name=h_font),
        body_font=FontConfig(name=b_font),
        numeric_font=FontConfig(name=h_font),
        hero_title_size=36,
        slide_title_size=28,
        subtitle_size=14,
        body_size=13,
        caption_size=10,
        kpi_number_size=38,
    )

    return DesignSystem(
        subject_domain=theme["domain"],
        visual_tone="executive" if theme["domain"] in ("finance", "legal_gov") else "editorial",
        colors=palette,
        typography=typography,
        card_corner_radius=float(theme.get("radius", 0.08)),
        card_stroke=False,
    )
