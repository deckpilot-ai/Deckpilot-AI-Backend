"""Design intelligence and dynamic design system generator agent."""

import logging
import re
from typing import Any

from app.schemas.generation_state import (
    ColorPalette,
    DesignSystem,
    FontConfig,
    PresentationGoal,
    TypographyHierarchy,
)
from app.skills.skill_registry import get_skill_for_request

logger = logging.getLogger(__name__)


class DesignIntelligenceAgent:
    """Infers complete visual language and generates structured DesignSystem object."""

    # High-quality font pairing catalog
    FONT_PAIRINGS = {
        "modern_sans": (FontConfig(name="Segoe UI"), FontConfig(name="Segoe UI")),
        "corporate_clean": (FontConfig(name="Calibri"), FontConfig(name="Calibri")),
        "editorial_serif": (FontConfig(name="Georgia"), FontConfig(name="Calibri")),
        "tech_geometric": (FontConfig(name="Segoe UI"), FontConfig(name="Segoe UI")),
    }

    # Dynamic palette collections
    PALETTES_BY_DOMAIN = {
        "tech": ColorPalette(
            primary="#0F172A",
            secondary="#1E293B",
            accent="#0284C7",
            neutral="#F0F9FF",
            background="#FFFFFF",
            card_fill="#F8FAFC",
            text_primary="#0F172A",
            text_secondary="#475569",
            chart_colors=["#0284C7", "#38BDF8", "#0EA5E9", "#6366F1", "#10B981", "#F59E0B"],
        ),
        "finance": ColorPalette(
            primary="#0F2922",
            secondary="#132E27",
            accent="#059669",
            neutral="#F0FDF4",
            background="#FFFFFF",
            card_fill="#F4FBF7",
            text_primary="#0F2922",
            text_secondary="#334155",
            chart_colors=["#059669", "#10B981", "#34D399", "#2563EB", "#F59E0B", "#6B7280"],
        ),
        "executive": ColorPalette(
            primary="#132A52",
            secondary="#1E3A8A",
            accent="#2563EB",
            neutral="#EEF2F8",
            background="#FFFFFF",
            card_fill="#F8FAFC",
            text_primary="#0F172A",
            text_secondary="#475569",
            chart_colors=["#2563EB", "#38BDF8", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"],
        ),
        "research": ColorPalette(
            primary="#3D2619",
            secondary="#5C3A24",
            accent="#D97706",
            neutral="#FDFBF7",
            background="#FFFFFF",
            paper="#FCF9F4",
            card_fill="#FBF8F3",
            text_primary="#291A10",
            text_secondary="#574336",
            chart_colors=["#D97706", "#B45309", "#92400E", "#2563EB", "#059669", "#6B7280"],
        ),
        "healthcare": ColorPalette(
            primary="#134E4A",
            secondary="#115E59",
            accent="#0D9488",
            neutral="#F0FDFA",
            background="#FFFFFF",
            card_fill="#F4FBF9",
            text_primary="#134E4A",
            text_secondary="#334155",
            chart_colors=["#0D9488", "#14B8A6", "#2DD4BF", "#0284C7", "#10B981", "#F59E0B"],
        ),
    }

    @classmethod
    def generate_design_system(
        cls,
        goal: PresentationGoal,
        reference_profile: dict[str, Any] | None = None,
        llm_brand_hints: dict[str, Any] | None = None,
    ) -> DesignSystem:
        topic_lower = goal.topic.lower()
        p_type = goal.presentation_type.value.lower() if hasattr(goal.presentation_type, "value") else str(goal.presentation_type).lower()
        skill = get_skill_for_request(goal.topic, p_type)

        # Determine subject domain
        if "tech" in p_type or "architecture" in p_type or "ai" in topic_lower or "cloud" in topic_lower:
            domain_key = "tech"
        elif "finance" in p_type or "revenue" in topic_lower or "budget" in topic_lower or "economy" in topic_lower:
            domain_key = "finance"
        elif "history" in topic_lower or "research" in p_type or "maratha" in topic_lower:
            domain_key = "history"
        elif "health" in topic_lower or "medical" in topic_lower:
            domain_key = "healthcare"
        elif "federal" in topic_lower or "governance" in topic_lower or "civic" in topic_lower:
            domain_key = "governance"
        else:
            domain_key = "executive"

        # 1. Determine base palette from PaletteGenerator
        from app.services.deck_archetypes import PaletteGenerator
        tokens = PaletteGenerator.generate_palette(goal.topic)
        
        colors = ColorPalette(
            ink=tokens.ink,
            primary=tokens.primary,
            secondary=tokens.secondary,
            accent=tokens.primary,
            tint_a=tokens.tint_a,
            tint_b=tokens.tint_b,
            alert=tokens.alert,
            neutral=tokens.tint_a,
            background="#FFFFFF",
            paper="#FAFAF9",
            card_fill=tokens.tint_a,
            text_primary=tokens.ink,
            text_secondary="#475569",
        )

        # 2. Learn from reference PPT profile if present
        ref_fonts = (reference_profile or {}).get("fonts", {})
        dominant_title = ref_fonts.get("dominant_title_font") or "Cambria"
        dominant_body = ref_fonts.get("dominant_body_font") or "Calibri"

        # Override colors if valid reference colors or LLM hints are provided
        ref_colors = (reference_profile or {}).get("colors", {})
        if ref_colors.get("primary_hint") and re.match(r"^#[0-9A-Fa-f]{6}$", ref_colors["primary_hint"]):
            colors.primary = ref_colors["primary_hint"]
            colors.accent = ref_colors["primary_hint"]
        if ref_colors.get("accent_hint") and re.match(r"^#[0-9A-Fa-f]{6}$", ref_colors["accent_hint"]):
            colors.secondary = ref_colors["accent_hint"]

        if llm_brand_hints and isinstance(llm_brand_hints, dict):
            hint_cols = llm_brand_hints.get("colors", {})
            if isinstance(hint_cols, dict):
                for k in ("ink", "primary", "secondary", "accent", "tint_a", "tint_b", "alert", "neutral"):
                    val = hint_cols.get(k)
                    if isinstance(val, str) and re.match(r"^#[0-9A-Fa-f]{6}$", val):
                        setattr(colors, k, val)

        typography = TypographyHierarchy(
            title_font=FontConfig(name=dominant_title),
            body_font=FontConfig(name=dominant_body),
            numeric_font=FontConfig(name=dominant_title),
            hero_title_size=36,
            slide_title_size=28,
            subtitle_size=14,
            body_size=13,
            caption_size=10,
            kpi_number_size=38,
        )

        return DesignSystem(
            version="2.0.0",
            subject_domain=domain_key,
            visual_tone=goal.tone,
            colors=colors,
            typography=typography,
            card_corner_radius=0.08,
            slide_width_inches=13.333,
            slide_height_inches=7.5,
            margin_left_inches=0.6,
            margin_top_inches=0.5,
            margin_right_inches=0.6,
            margin_bottom_inches=0.6,
            visual_density="balanced",
        )
