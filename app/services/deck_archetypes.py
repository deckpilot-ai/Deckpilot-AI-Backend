"""High-Fidelity Consulting Deck Archetypes, Grid Geometry, and Palette Engine.

Reverse-engineered from consulting-grade benchmark decks (250+ slides, 13.333"x7.5")
matching the deck-agent-package design system specification.
"""

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Fixed Canvas Dimensions (Widescreen 16:9)
CANVAS_WIDTH_IN: float = 13.333
CANVAS_HEIGHT_IN: float = 7.5

# Fixed Grid Vertical Rhythm (both Family A and Family B)
GRID_SPEC = {
    "eyebrow": {
        "x": 0.6,
        "y": 0.5,
        "w": 12.1,
        "h": 0.35,
        "font_size_pt": 12,
        "font": "Calibri",
        "bold": True,
        "uppercase": True,
    },
    "title": {
        "x": 0.6,
        "y": 0.85,
        "w": 12.1,
        "h": 0.8,
        "font_size_pt": 30,
        "font": "Cambria",
        "bold": True,
    },
    "accent_tick": {
        "x": 0.6,
        "y": 1.72,
        "w": 0.6,
        "h": 0.06,
        "color_token": "primary",
    },
    "content_start_y": 1.95,
    "footer_y": 7.05,
    "footer_left": {
        "x": 0.6,
        "y": 7.05,
        "w": 11.0,
        "h": 0.3,
        "font_size_pt": 9.5,
        "color": "#6B7A78",
    },
    "footer_page_badge": {
        "x": 12.25,
        "y": 6.95,
        "w": 0.45,
        "h": 0.45,
        "font_size_pt": 10,
        "bold": True,
    },
    "margins_in": {
        "left": 0.6,
        "right": 0.6,
        "top": 0.5,
        "bottom": 0.45,
    },
}

# Typography Pairings (Zero QA Risk Pairing)
TYPOGRAPHY_CONFIG = {
    "title_font": "Cambria",
    "body_font": "Calibri",
    "numeric_font": "Cambria",
}


@dataclass
class ColorTokens:
    ink: str = "#0C3B39"         # Dark background / headline text
    primary: str = "#0E7C7B"     # Main accent (icons, numbers, active cards)
    secondary: str = "#16A085"   # Second accent (alternating elements)
    tint_a: str = "#E9F3F1"      # Light card/panel background (~90% lightened)
    tint_b: str = "#F6EFE2"      # Second light background (alternating rows)
    alert: str = "#C63A28"       # Contrast / negative case / highlight
    background: str = "#FFFFFF"  # Slide paper background

    def to_dict(self) -> dict[str, str]:
        return {
            "ink": self.ink,
            "primary": self.primary,
            "secondary": self.secondary,
            "tint_a": self.tint_a,
            "tint_b": self.tint_b,
            "alert": self.alert,
            "background": self.background,
        }


# Curated, proven benchmark palettes derived from real reference decks
BENCHMARK_PALETTES = {
    "federalism": ColorTokens(
        ink="#0C3B39", primary="#0E7C7B", secondary="#16A085",
        tint_a="#E9F3F1", tint_b="#F4FBF9", alert="#C63A28",
    ),
    "marathas": ColorTokens(
        ink="#7E2C22", primary="#E4791F", secondary="#6B221C",
        tint_a="#F7EEE3", tint_b="#FBF6EF", alert="#C63A28",
    ),
    "economy": ColorTokens(
        ink="#1F3864", primary="#2F5597", secondary="#5B9BD5",
        tint_a="#EEF2F8", tint_b="#F8FAFC", alert="#C00000",
    ),
    "constitution": ColorTokens(
        ink="#13294B", primary="#1E3A8A", secondary="#3B82F6",
        tint_a="#EEF4F8", tint_b="#F5F8FA", alert="#B91C1C",
    ),
    "markets": ColorTokens(
        ink="#132A52", primary="#2563EB", secondary="#0284C7",
        tint_a="#EEF2F8", tint_b="#F8FAFC", alert="#DC2626",
    ),
    "healthcare": ColorTokens(
        ink="#134E4A", primary="#0D9488", secondary="#14B8A6",
        tint_a="#F0FDFA", tint_b="#F4FBF9", alert="#E11D48",
    ),
    "technology": ColorTokens(
        ink="#0F172A", primary="#0284C7", secondary="#38BDF8",
        tint_a="#F0F9FF", tint_b="#F8FAFC", alert="#EF4444",
    ),
    "governance": ColorTokens(
        ink="#0C3B39", primary="#0E7C7B", secondary="#16A085",
        tint_a="#E9F3F1", tint_b="#F4FBF9", alert="#DC2626",
    ),
    "indigo": ColorTokens(
        ink="#1E1B4B", primary="#4F46E5", secondary="#818CF8",
        tint_a="#EEF2FF", tint_b="#F5F3FF", alert="#E11D48",
    ),
    "emerald": ColorTokens(
        ink="#064E3B", primary="#059669", secondary="#10B981",
        tint_a="#ECFDF5", tint_b="#F0FDF4", alert="#DC2626",
    ),
    "obsidian": ColorTokens(
        ink="#090D16", primary="#38BDF8", secondary="#0284C7",
        tint_a="#0F172A", tint_b="#1E293B", alert="#F43F5E",
    ),
}


class PaletteGenerator:
    """Generates a 5-6 token topic-derived color palette per deck-agent-package rule."""

    @staticmethod
    def generate_palette(
        topic: str,
        tone: str = "warm_editorial",
        style_family: Literal["A", "B"] = "A",
    ) -> ColorTokens:
        topic_lower = topic.lower()

        # 1. Explicit user theme/color directives have highest priority
        if any(w in topic_lower for w in ("blue", "navy", "royal blue", "sky blue", "modern indigo")):
            if "indigo" in topic_lower:
                return BENCHMARK_PALETTES["indigo"]
            return BENCHMARK_PALETTES["markets"]
        if any(w in topic_lower for w in ("obsidian", "dark mode", "dark theme", "black")):
            return BENCHMARK_PALETTES["obsidian"]
        if any(w in topic_lower for w in ("emerald", "green", "mint", "forest")):
            return BENCHMARK_PALETTES["emerald"]
        if any(w in topic_lower for w in ("teal", "cyan", "medical", "clinical")):
            return BENCHMARK_PALETTES["healthcare"]
        if any(w in topic_lower for w in ("saffron", "maratha", "orange", "terracotta", "shivaji", "peshwa")):
            return BENCHMARK_PALETTES["marathas"]

        # 2. Semantic domain matching
        if any(w in topic_lower for w in ("federal", "civic", "constitution", "parliament", "democracy", "government", "policy")):
            return BENCHMARK_PALETTES["federalism"]
        if any(w in topic_lower for w in ("economy", "market", "finance", "fiscal", "revenue", "trade", "banking", "sector")):
            return BENCHMARK_PALETTES["economy"]
        if any(w in topic_lower for w in ("health", "medical", "clinical", "biotech", "pharma", "patient")):
            return BENCHMARK_PALETTES["healthcare"]
        if any(w in topic_lower for w in ("tech", "cloud", "saas", "software", "ai", "data", "platform", "kubernetes")):
            return BENCHMARK_PALETTES["technology"]
        if any(w in topic_lower for w in ("sustainab", "environment", "climate", "energy", "green")):
            return BENCHMARK_PALETTES["governance"]

        if style_family == "B" or tone in ("formal_government", "institutional"):
            return BENCHMARK_PALETTES["constitution"]

        return BENCHMARK_PALETTES["markets"]


# Catalog of 23 layout archetypes matching layout_archetypes.json
LAYOUT_ARCHETYPES = {
    "A1": {
        "family": "A",
        "name": "Title Cover - Blob Variant",
        "category": "title",
        "when_to_use": "Deck opening slide, editorial family",
        "schema_keys": ["eyebrow", "title", "subtitle", "pills", "footer_note"],
    },
    "A2": {
        "family": "A",
        "name": "Title Cover - Split Panel",
        "category": "title",
        "when_to_use": "Deck opening slide when a strong hero photo exists",
        "schema_keys": ["eyebrow", "title", "subtitle", "chapter_tag", "image_ref", "figure_caption"],
    },
    "A3": {
        "family": "B",
        "name": "Section Divider - Photo Hero",
        "category": "divider",
        "when_to_use": "Section break in an executive briefing deck",
        "schema_keys": ["brand_mark", "headline", "background_image"],
    },
    "A4": {
        "family": "A",
        "name": "Chapter Roadmap / Agenda",
        "category": "roadmap",
        "when_to_use": "Table-of-contents / agenda slide, 4-6 items",
        "schema_keys": ["eyebrow", "title", "items"],
    },
    "A5": {
        "family": "A",
        "name": "Core Definition",
        "category": "definition",
        "when_to_use": "Introducing or defining a key concept or term",
        "schema_keys": ["eyebrow", "title", "definition", "attributes", "why_it_matters"],
    },
    "A6": {
        "family": "A",
        "name": "Two-Entity Comparison Cards",
        "category": "comparison",
        "when_to_use": "Comparing two named entities or cases (systems, states, options)",
        "schema_keys": ["entity_a", "entity_b"],
    },
    "A7": {
        "family": "A",
        "name": "Two-Column Contrast (Concepts)",
        "category": "comparison",
        "when_to_use": "Concept-vs-concept contrast (no heavy header bars)",
        "schema_keys": ["left", "right"],
    },
    "A8": {
        "family": "A",
        "name": "Stat + Map/Image Highlight",
        "category": "stat_image",
        "when_to_use": "Pairing headline stats with a supporting figure, image, or map",
        "schema_keys": ["stats", "callout", "image_ref", "image_caption"],
    },
    "A9": {
        "family": "A",
        "name": "Process Chain with Value Row",
        "category": "process",
        "when_to_use": "Walking through a concrete worked example or value chain",
        "schema_keys": ["intro_paragraph", "steps", "closing_band"],
    },
    "A10": {
        "family": "A",
        "name": "Numbered Process Row (3 steps)",
        "category": "process",
        "when_to_use": "Simple 3-step sequential narrative",
        "schema_keys": ["steps"],
    },
    "A11": {
        "family": "A",
        "name": "Stage / Maturity Columns",
        "category": "process",
        "when_to_use": "Progression-over-time / maturity-stage narrative (3-5 stages)",
        "schema_keys": ["stages"],
    },
    "A12": {
        "family": "A",
        "name": "Before / After Pair",
        "category": "comparison",
        "when_to_use": "Contrasting a start-state and an end-state",
        "schema_keys": ["before", "after"],
    },
    "A13": {
        "family": "A",
        "name": "2x2 / 2x3 Icon-Numbered Grid",
        "category": "grid",
        "when_to_use": "4-6 parallel reasons, causes, or factors with no strict sequence",
        "schema_keys": ["items"],
    },
    "A14": {
        "family": "A",
        "name": "Chart + Insight Panel",
        "category": "chart",
        "when_to_use": "Any slide whose core content is numeric data needing a chart",
        "schema_keys": ["chart_title", "chart_type", "chart_data", "insight_label", "insight_text", "highlight_stat"],
    },
    "A15": {
        "family": "A",
        "name": "Dual Big-Stat Comparison",
        "category": "stats",
        "when_to_use": "The core insight is two contrasting numbers or metrics",
        "schema_keys": ["left", "right"],
    },
    "A16": {
        "family": "A_or_B",
        "name": "Native Data Table",
        "category": "table",
        "when_to_use": "Cause-effect matrices, classification tables, status trackers",
        "schema_keys": ["headers", "rows", "row_note"],
    },
    "A17": {
        "family": "A",
        "name": "Closing Takeaways (Accent Bar)",
        "category": "closing",
        "when_to_use": "Final summary / takeaways slide with accent bar on left edge",
        "schema_keys": ["eyebrow", "title", "body", "closing_line"],
    },
    "A18": {
        "family": "A",
        "name": "Recap Checklist",
        "category": "closing",
        "when_to_use": "Very last recap slide before closing",
        "schema_keys": ["eyebrow", "title", "items", "closing_tagline"],
    },
    "A19": {
        "family": "A",
        "name": "Glossary Grid",
        "category": "glossary",
        "when_to_use": "Definition-list content only (8-10 terms)",
        "schema_keys": ["terms"],
    },
    "A20": {
        "family": "A_or_B",
        "name": "Org / Hierarchy Diagram",
        "category": "hierarchy",
        "when_to_use": "Org charts, council structures, governance tiers",
        "schema_keys": ["centerpiece", "roles"],
    },
    "A21": {
        "family": "B",
        "name": "KPI Cluster",
        "category": "stats",
        "when_to_use": "Achievement or highlight-numbers cluster, Family B only",
        "schema_keys": ["stats"],
    },
    "A22": {
        "family": "B",
        "name": "Hub-and-Spoke System Diagram",
        "category": "diagram",
        "when_to_use": "Integration / ecosystem-overview (central hub with peripheral nodes)",
        "schema_keys": ["hub_label", "spokes"],
    },
    "A23": {
        "family": "B",
        "name": "Vertical Layered Pipeline",
        "category": "architecture",
        "when_to_use": "Architecture / data-flow explainer with stacked horizontal bars",
        "schema_keys": ["layers", "feedback_loop_label"],
    },
    "A24": {
        "family": "A",
        "name": "Chronology / Horizontal Timeline Band",
        "category": "timeline",
        "when_to_use": "Historical milestones, evolution over time, chronological sequence (4-5 key dates)",
        "schema_keys": ["eyebrow", "title", "milestones", "connector_label"],
    },
    "A25": {
        "family": "A_or_B",
        "name": "Council of Eight / 8-Feature Governance Grid",
        "category": "hierarchy",
        "when_to_use": "Ashta Pradhana Mandala, 6-8 constitutional powers, 7-8 pillar features",
        "schema_keys": ["eyebrow", "title", "roles", "summary_note"],
    },
    "A26": {
        "family": "A",
        "name": "Two Highways / Dual Route Map Split",
        "category": "comparison",
        "when_to_use": "Two contrasting strategic routes or models paired with a framed documentary map/figure",
        "schema_keys": ["eyebrow", "title", "route_a", "route_b", "image_ref", "caption"],
    },
    "A27": {
        "family": "A",
        "name": "Core State Quote with Emblem Disc",
        "category": "quote",
        "when_to_use": "Authoritative historical or strategic quote paired with structured operational pillars",
        "schema_keys": ["eyebrow", "title", "pillars", "quote_text", "quote_author"],
    },
    "A28": {
        "family": "A",
        "name": "Concept Definition Card with Photo Mat",
        "category": "definition",
        "when_to_use": "Foundational term or doctrine definition paired with a documentary artifact photo",
        "schema_keys": ["eyebrow", "title", "definition", "attributes", "image_ref", "caption"],
    },
    "A29": {
        "family": "A",
        "name": "The Big Questions (4 Hero Numbered Cards)",
        "category": "roadmap",
        "when_to_use": "Chapter roadmap, scene setting, or inquiry-led opening with 4 numbered questions",
        "schema_keys": ["eyebrow", "title", "questions"],
    },
    "A30": {
        "family": "A",
        "name": "Stepped Value Chain / Journey of Goods Flow",
        "category": "process",
        "when_to_use": "End-to-end value chain, market trade journey, supply chain stages (4-5 steps)",
        "schema_keys": ["eyebrow", "title", "steps", "summary_band"],
    },
}


class ArchetypeSelector:
    """Selects the best layout archetype for a content block, enforcing the non-repeat rule."""

    CONTENT_TYPE_MAP: dict[str, list[str]] = {
        "title": ["A1", "A2"],
        "divider": ["A3"],
        "roadmap": ["A4", "A29"],
        "agenda": ["A4", "A29"],
        "big_questions": ["A29", "A4", "A13"],
        "questions": ["A29", "A13"],
        "definition": ["A5", "A28", "A19"],
        "concept_definition": ["A28", "A5"],
        "comparison_entities": ["A6", "A26", "A12"],
        "comparison_concepts": ["A7", "A12", "A6"],
        "comparison": ["A6", "A26", "A7", "A12"],
        "two_highways": ["A26", "A6"],
        "two_routes": ["A26", "A6"],
        "stat_highlight": ["A8", "A15", "A21"],
        "stats": ["A15", "A8", "A21"],
        "timeline": ["A24", "A11", "A4"],
        "chronology": ["A24", "A11"],
        "history_timeline": ["A24", "A11"],
        "process_sequence": ["A10", "A30", "A9", "A11"],
        "process": ["A10", "A30", "A9", "A11"],
        "value_chain": ["A30", "A9", "A10"],
        "market_chain": ["A30", "A9"],
        "stage_progression": ["A11", "A30", "A10"],
        "grid_reasons": ["A13", "A25"],
        "grid": ["A13", "A25"],
        "council_eight": ["A25", "A20", "A13"],
        "ashta_pradhana": ["A25", "A20"],
        "governance_council": ["A25", "A20"],
        "quote": ["A27", "A17"],
        "quote_emblem": ["A27", "A17"],
        "core_state_quote": ["A27", "A17"],
        "chart_insight": ["A14"],
        "chart": ["A14"],
        "table_data": ["A16"],
        "table": ["A16"],
        "takeaways": ["A17", "A18"],
        "closing": ["A17", "A18"],
        "recap": ["A18", "A17"],
        "org_hierarchy": ["A20", "A25"],
        "system_diagram": ["A22"],
        "hub_spoke": ["A22", "A25"],
        "pipeline_architecture": ["A23"],
    }

    @classmethod
    def select_archetype(
        cls,
        content_type: str,
        content_summary: str = "",
        previous_archetype: str | None = None,
        style_family: Literal["A", "B"] = "A",
        has_image: bool = False,
        has_chart: bool = False,
        has_table: bool = False,
    ) -> str:
        """Select an archetype from catalog, avoiding back-to-back repeats."""
        # Hardware overrides
        if has_chart:
            return "A14"
        if has_table:
            return "A16"
        if has_image and content_type == "title":
            return "A2"
        if has_image and content_type in ("stat_highlight", "stats", "two_column"):
            return "A8"

        candidates = cls.CONTENT_TYPE_MAP.get(content_type.lower(), ["A13", "A7", "A10"])

        # Filter by family if specific to B
        filtered = []
        for c in candidates:
            arch = LAYOUT_ARCHETYPES.get(c, {})
            fam = arch.get("family", "A")
            if style_family == "A" and fam == "B":
                continue
            if style_family == "B" and fam == "A" and c in ("A1", "A4"):
                continue
            filtered.append(c)

        if not filtered:
            filtered = candidates

        # Avoid repeating the immediate predecessor
        if previous_archetype and len(filtered) > 1 and filtered[0] == previous_archetype:
            return filtered[1]

        return filtered[0] if filtered else "A13"
