"""Layout Archetypes for Federalism Editorial Theme (F01–F27).

Implements the 24 reference slide layouts from 'Federalism (2).pptx' plus
3 chronological timeline extensions (F25, F26, F27).
"""

from typing import Any, Dict, List, Optional
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from app.presentation.themes.federalism_editorial.tokens import COLORS, FONTS, GEOMETRY
from app.presentation.themes.federalism_editorial.components import (
    SlideKicker, SlideTitle, SlideSubtitle, SlideFooter, TitleAccentBar,
    IconBadge, InfoCard, CreamCard, DarkCard, NegativeCard, MetricCard,
    HorizontalMetricCard, ImageFrame, MapFrame, EditorialQuoteCard, Pill,
    TimelineNode, TimelineTrack, FeatureContainerCard, add_text_box, create_solid_shape
)


def _set_light_background(slide: Any):
    """Fills slide background with crisp white canvas."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = COLORS.rgb_white


def _set_dark_background(slide: Any, with_abstract_circles: bool = True):
    """Fills slide with deep teal canvas and optional subtle low-contrast watermark circles."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = COLORS.rgb_dark

    if with_abstract_circles:
        # Subtle large watermark circles that bleed past slide edges (low contrast)
        c1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.50), Inches(-1.50), Inches(5.80), Inches(5.80))
        c1.fill.solid()
        c1.fill.fore_color.rgb = COLORS.rgb_dark_alt
        c1.line.fill.background()

        c2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-1.20), Inches(4.50), Inches(4.60), Inches(4.60))
        c2.fill.solid()
        c2.fill.fore_color.rgb = COLORS.rgb_dark_alt
        c2.line.fill.background()


class FederalismLayouts:
    """Complete catalog of 27 coded layout archetypes for Federalism Editorial theme."""

    # ──────────────────────────────────────────────────────────────────────────
    # F01: Dark Cover Hero
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f01(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide, with_abstract_circles=True)

        kicker = data.get("kicker", "CHAPTER 2")
        SlideKicker.render(slide, kicker, is_dark=True, x=0.90, y=1.55)

        title = data.get("title", "Federalism")
        tb_t = add_text_box(slide, 0.85, 1.95, 11.50, 1.70)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = str(title).strip()
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(56.0)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_white

        subtitle = data.get("subtitle") or data.get("lead", "Sharing power across the levels of government")
        tb_s = add_text_box(slide, 0.90, 3.75, 10.50, 0.80)
        p_s = tb_s.text_frame.paragraphs[0]
        p_s.text = str(subtitle).strip()
        p_s.font.name = FONTS.body
        p_s.font.size = Pt(18.0)
        p_s.font.color.rgb = COLORS.rgb_text_on_dark

        # Metadata pill
        meta = data.get("metadata", "Class 10  |  Democratic Politics")
        Pill.render(slide, 0.90, 5.15, meta, variant="teal", height=0.40)

        # Context badge line at bottom
        footer_text = data.get("footer", "A study of India's three-tier system of government")
        IconBadge.render(slide, 0.90, 6.10, diameter=0.48, bg_color=COLORS.rgb_primary_teal,
                         title=footer_text, icon_bytes=images.get("image-1-1.png"))
        tb_f = add_text_box(slide, 1.55, 6.18, 10.00, 0.35)
        p_f = tb_f.text_frame.paragraphs[0]
        p_f.text = str(footer_text).strip()
        p_f.font.name = FONTS.body
        p_f.font.size = Pt(11.5)
        p_f.font.color.rgb = COLORS.rgb_text_on_dark

    # ──────────────────────────────────────────────────────────────────────────
    # F02: Vertical Roadmap
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f02(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CHAPTER ROADMAP"))
        SlideTitle.render(slide, data.get("title", "What This Chapter Covers"))

        items = data.get("items", [
            {"title": "The idea of federalism", "body": "What it is, key features, and two routes to formation"},
            {"title": "Federalism around the world", "body": "How 25 countries govern 40% of the world's population"},
            {"title": "What makes India federal", "body": "The constitutional distribution of powers: three legislative lists"},
            {"title": "How federalism is practised", "body": "Linguistic states, language policy, and coalition politics"},
            {"title": "Decentralisation in India", "body": "The landmark 1992 amendment and the third tier of democracy"}
        ])[:5]

        y_start = 2.15
        gap = 0.92
        for i, it in enumerate(items):
            y = y_start + (i * gap)
            is_cream = (i % 2 == 1)
            InfoCard.render(slide, 0.70, y, 11.90, 0.82,
                            title=it.get("title"), body=it.get("body"),
                            ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                            default_index=i, is_cream=is_cream)

        SlideFooter.render(slide, data.get("page_num", 2), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F03: Definition + Government Levels + Principles
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f03(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE CORE IDEA"))
        SlideTitle.render(slide, data.get("title", "What Is Federalism?"))

        # Left Dark Definition Card
        def_text = data.get("def_body") or data.get("definition", "Federalism is a system of government in which power is divided between a central authority and constituent units.")
        DarkCard.render(slide, 0.70, 2.05, 5.80, 2.65,
                        title=data.get("def_title", "Core Definition"), body=def_text,
                        icon_color=COLORS.rgb_accent_orange, default_index=0)

        # Right 2 Supporting Cards
        levels = data.get("levels", [])
        sub1 = levels[0] if len(levels) > 0 else data.get("level1", {"title": "Central Level", "body": "Usually responsible for subjects of common national interest."})
        sub2 = levels[1] if len(levels) > 1 else data.get("level2", {"title": "State / Regional Level", "body": "Looks after much of the day-to-day administration of their province."})
        InfoCard.render(slide, 6.80, 2.05, 5.80, 1.22,
                        title=sub1.get("title"), body=sub1.get("body"),
                        icon_color=COLORS.rgb_primary_teal, default_index=1)
        InfoCard.render(slide, 6.80, 3.48, 5.80, 1.22,
                        title=sub2.get("title"), body=sub2.get("body"),
                        icon_color=COLORS.rgb_secondary_teal, default_index=2)

        # Wide Principles Container Below
        raw_principles = data.get("principles", [
            {"title": "Mutual Trust", "body": "Governments must agree to live together."},
            {"title": "Autonomy", "body": "Independent jurisdictions defined in law."},
            {"title": "Dual Objectives", "body": "Safeguard unity while accommodating diversity."}
        ])

        if isinstance(raw_principles, list):
            FeatureContainerCard.render(slide, 0.70, 4.88, 11.90, 1.82,
                                        title=data.get("principles_title", "Core Principles of Federalism"),
                                        items=raw_principles, is_cream=True, default_index=3)
        else:
            CreamCard.render(slide, 0.70, 4.88, 11.90, 1.82,
                             title=data.get("principles_title", "Core Principles of Federalism"),
                             body=str(raw_principles),
                             icon_color=COLORS.rgb_accent_orange, default_index=3)

        SlideFooter.render(slide, data.get("page_num", 3), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F04: Two-System Comparison (Side-by-side cards)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f04(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "A TALE OF TWO SYSTEMS"))
        SlideTitle.render(slide, data.get("title", "Belgium and Sri Lanka"))

        # Left Card: Belgium (Positive Federal)
        card1 = data.get("left") or data.get("card1", {
            "title": "Belgium: Power Shared",
            "body": "Leaders amended their constitution four times to ensure all communities share governance. Result: peace and economic unity.",
            "status": "FEDERAL SUCCESS"
        })
        p1 = card1.get("pill") or card1.get("status", "FEDERAL SUCCESS")
        b1 = card1.get("points")
        InfoCard.render(slide, 0.70, 2.05, 5.80, 4.60,
                        title=card1.get("title"), body=card1.get("body"),
                        icon_color=COLORS.rgb_primary_teal, default_index=0,
                        pill=p1, pill_variant="teal", bullets=b1)

        # Right Card: Sri Lanka (Unitary Conflict)
        card2 = data.get("right") or data.get("card2", {
            "title": "Sri Lanka: Centralized Rule",
            "body": "Majoritarian policies refused to share power with Tamils. Result: decades of civil war and deep national division.",
            "status": "UNITARY FAILURE"
        })
        p2 = card2.get("pill") or card2.get("status", "UNITARY FAILURE")
        b2 = card2.get("points")
        NegativeCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                            title=card2.get("title"), body=card2.get("body"),
                            default_index=1,
                            pill=p2, pill_variant="negative", bullets=b2)

        SlideFooter.render(slide, data.get("page_num", 4), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F05: Metrics + Large Map/Image
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f05(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "A GLOBAL PERSPECTIVE"))
        SlideTitle.render(slide, data.get("title", "Federations Around the World"))

        # Left KPIs
        MetricCard.render(slide, 0.70, 2.05, 4.40, 1.50,
                          value=data.get("kpi1_val", "25"),
                          label=data.get("kpi1_lbl", "Federal Countries"),
                          subtext="Out of 193 UN member nations worldwide.")

        MetricCard.render(slide, 0.70, 3.75, 4.40, 1.50,
                          value=data.get("kpi2_val", "40%"),
                          label=data.get("kpi2_lbl", "World Population"),
                          subtext="Governed under federal democratic frameworks.",
                          is_cream=True)

        DarkCard.render(slide, 0.70, 5.45, 4.40, 1.25,
                        title="Global Scale",
                        body=data.get("insight", "Most large, diverse democracies operate on federal models."),
                        icon_color=COLORS.rgb_accent_orange, default_index=0)

        # Right Framed Map
        map_img = images.get("image-5-1.png") or images.get("map_bytes") or images.get("image_id")
        MapFrame.render(slide, 5.40, 2.05, 7.20, 4.65,
                        map_bytes=map_img, caption="Global map highlighting the 25 major federal democracies.")

        SlideFooter.render(slide, data.get("page_num", 5), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F06: Split Comparison List (Federal vs Unitary)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f06(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TWO WAYS TO ORGANISE A STATE"))
        SlideTitle.render(slide, data.get("title", "Federal vs Unitary Government"))

        # Left Panel (Federal System)
        fed_items = data.get("federal_items", [
            "Two or more levels of government exist together",
            "Central government cannot order state governments arbitrarily",
            "States have autonomous constitutional powers",
            "Both levels are directly answerable to citizens"
        ])
        fed_body = "\n• " + "\n• ".join(fed_items)
        InfoCard.render(slide, 0.70, 2.05, 5.80, 4.60,
                        title="Federal System", body=fed_body,
                        icon_color=COLORS.rgb_primary_teal, default_index=0)

        # Right Panel (Unitary System)
        unit_items = data.get("unitary_items", [
            "Only one level of government holds primary power",
            "Sub-units are subordinate to the central authority",
            "Central authority can pass down binding decrees",
            "Power can be recalled by central executive at will"
        ])
        unit_body = "\n• " + "\n• ".join(unit_items)
        CreamCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                         title="Unitary System", body=unit_body,
                         icon_color=COLORS.rgb_accent_orange, default_index=1)

        SlideFooter.render(slide, data.get("page_num", 6), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F07: Multi-Feature Grid (7 Key Features, 3 Columns)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f07(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE BUILDING BLOCKS"))
        SlideTitle.render(slide, data.get("title", "Seven Key Features of Federalism"))

        features = data.get("items", [
            {"title": "Multiple Levels", "body": "Two or more distinct tiers of government govern the same citizenry."},
            {"title": "Jurisdiction", "body": "Each tier has demarcated legislative, taxation, and administrative fields."},
            {"title": "Constitutional Guarantee", "body": "Existence and authority of each level is constitutionally protected."},
            {"title": "Bilateral Consent", "body": "Fundamental provisions cannot be unilaterally amended by one level."},
            {"title": "Judicial Umpire", "body": "Supreme and high courts interpret the constitution and resolve disputes."},
            {"title": "Financial Autonomy", "body": "Revenue sources for each level are specified to ensure fiscal independence."}
        ])[:6]

        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 1.85

        for i, f in enumerate(features):
            col = i % 3
            row = i // 3
            y = 2.05 + (row * 1.95)
            InfoCard.render(slide, x_coords[col], y, w, h,
                            title=f.get("title"), body=f.get("body"),
                            ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                            default_index=i)

        # 7th Feature: Full width strip below if provided
        f7 = data.get("feature_7", "Dual Objectives: Promoting national unity while safeguarding regional cultural and administrative diversity.")
        CreamCard.render(slide, 0.70, 6.00, 11.90, 0.75,
                         title="Objective 7", body=f7,
                         icon_color=COLORS.rgb_accent_orange, default_index=6)

        SlideFooter.render(slide, data.get("page_num", 7), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F08: Two Large Category Cards (Coming Together vs Holding Together)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f08(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "HOW FEDERATIONS ARE FORMED"))
        SlideTitle.render(slide, data.get("title", "Two Routes to a Federation"))

        # Left Card: Coming Together
        c1 = data.get("route1", {
            "title": "Coming Together Federations",
            "body": "Independent states pool sovereignty together to form a bigger unit, enhancing common security while retaining individual identity.",
            "examples": "USA, Switzerland, Australia"
        })
        ex1 = c1.get("examples") or "USA, Switzerland, Australia"
        InfoCard.render(slide, 0.70, 2.05, 5.80, 4.60,
                        title=c1.get("title"), body=c1.get("body"),
                        icon_color=COLORS.rgb_primary_teal, default_index=0,
                        bottom_pill=f"Examples: {ex1}", bottom_pill_variant="teal")

        # Right Card: Holding Together
        c2 = data.get("route2", {
            "title": "Holding Together Federations",
            "body": "A large country decides to divide power between constituent states and the national government. Central government is often more powerful.",
            "examples": "India, Spain, Belgium"
        })
        ex2 = c2.get("examples") or "India, Spain, Belgium"
        CreamCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                         title=c2.get("title"), body=c2.get("body"),
                         icon_color=COLORS.rgb_accent_orange, default_index=1,
                         bottom_pill=f"Examples: {ex2}", bottom_pill_variant="orange")

        SlideFooter.render(slide, data.get("page_num", 8), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F09: Three-Tier Structure (Connected Cards)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f09(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE INDIAN UNION"))
        SlideTitle.render(slide, data.get("title", "The Three Tiers of Indian Federalism"))

        # Overview Strip Top
        lead_text = data.get("lead", "The Constitution originally provided for a two-tier system of government. A third tier of Panchayats and Municipalities was added later.")
        DarkCard.render(slide, 0.70, 2.05, 11.90, 1.05,
                        title="Constitutional Framework", body=lead_text,
                        icon_color=COLORS.rgb_accent_orange, default_index=0)

        # 3 Connected Tier Cards Below
        tiers = data.get("tiers", [
            {"tier": "TIER 1", "title": "Union Government", "body": "National authority representing the Indian Union across defense, foreign affairs, and finance."},
            {"tier": "TIER 2", "title": "State Governments", "body": "Autonomous state authorities managing police, trade, agriculture, and local health."},
            {"tier": "TIER 3", "title": "Local Self-Government", "body": "Grassroots democracy through Panchayats in rural areas and Municipalities in towns."}
        ])[:3]

        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 3.35
        for i, t in enumerate(tiers):
            card_col = COLORS.rgb_primary_teal if i == 0 else (COLORS.rgb_secondary_teal if i == 1 else COLORS.rgb_accent_orange)
            tier_lbl = t.get("tier") or t.get("label")
            InfoCard.render(slide, x_coords[i], 3.30, w, h,
                            title=t.get("title"), body=t.get("body"),
                            pill=tier_lbl, pill_variant="teal" if i == 0 else ("orange" if i == 1 else "cream"),
                            ghost_no=str(i + 1) if not tier_lbl else None,
                            icon_color=card_col, default_index=i)

        SlideFooter.render(slide, data.get("page_num", 9), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F10: Three-Category List (Union, State, Concurrent)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f10(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "DISTRIBUTION OF LEGISLATIVE POWERS"))
        SlideTitle.render(slide, data.get("title", "The Three Lists of the Constitution"))

        lists = data.get("lists", [
            {
                "title": "Union List",
                "scope": "National Importance",
                "items": "• Defense of the nation\n• Foreign affairs & treaties\n• Banking & currency\n• Communications",
                "color": COLORS.rgb_primary_teal
            },
            {
                "title": "State List",
                "scope": "State & Local Importance",
                "items": "• Police & law enforcement\n• Trade & commerce\n• Agriculture & irrigation\n• Public health",
                "color": COLORS.rgb_secondary_teal
            },
            {
                "title": "Concurrent List",
                "scope": "Common Interest",
                "items": "• Education standards\n• Forests & environment\n• Trade unions & labour\n• Succession & marriage",
                "color": COLORS.rgb_accent_orange
            }
        ])[:3]

        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 3.75
        for i, l in enumerate(lists):
            scope = l.get("scope")
            items = l.get("items")
            body_val = l.get("body")
            if scope and items:
                content = f"{scope}\n\n{items}"
            elif items:
                content = items
            elif body_val:
                content = f"{scope}\n\n{body_val}" if scope else body_val
            else:
                content = ""

            pill_val = l.get("pill")
            card_col = l.get("color") or (COLORS.rgb_primary_teal if i == 0 else (COLORS.rgb_secondary_teal if i == 1 else COLORS.rgb_accent_orange))
            InfoCard.render(slide, x_coords[i], 2.05, w, h,
                            title=l.get("title"), body=content,
                            pill=pill_val, pill_variant="teal" if i == 0 else ("orange" if i == 1 else "cream"),
                            icon_color=card_col, default_index=i)

        # Full width residuary insight strip below
        residuary = data.get("residuary", "Residuary Subjects: Matters that do not fall in any list (e.g., cyber law, computer software) vest solely with the Union Parliament.")
        CreamCard.render(slide, 0.70, 6.00, 11.90, 0.75,
                         title="Residuary Powers", body=residuary,
                         icon_color=COLORS.rgb_accent_orange, default_index=3)

        SlideFooter.render(slide, data.get("page_num", 10), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F11: Dual Detail Panel (Special Status vs Union Territories)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f11(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "NOT ALL UNITS ARE EQUAL"))
        SlideTitle.render(slide, data.get("title", "Special Status and Union Territories"))

        # Left Panel (Teal): Special Status States
        left_p = data.get("panel1", {
            "title": "States with Special Status",
            "body": "Article 371 grants special asymmetric powers to certain northeastern states due to unique historical and indigenous land-holding rights.",
            "pill": "ARTICLE 371"
        })
        p1 = left_p.get("pill", "ARTICLE 371")
        InfoCard.render(slide, 0.70, 2.05, 5.80, 4.60,
                        title=left_p.get("title"), body=left_p.get("body"),
                        icon_color=COLORS.rgb_primary_teal, default_index=0,
                        pill=p1, pill_variant="teal")

        # Right Panel (Cream): Union Territories
        right_p = data.get("panel2", {
            "title": "Union Territories",
            "body": "Units too small to become independent states and impossible to merge with existing states. They do not hold state powers and are run directly by the Central Government.",
            "pill": "DIRECT CENTRAL RULE"
        })
        p2 = right_p.get("pill", "DIRECT CENTRAL RULE")
        CreamCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                         title=right_p.get("title"), body=right_p.get("body"),
                         icon_color=COLORS.rgb_accent_orange, default_index=1,
                         pill=p2, pill_variant="orange")

        SlideFooter.render(slide, data.get("page_num", 11), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F12: Step Flow + Dark Insight Panel
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f12(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "GUARDRAILS OF THE SYSTEM"))
        SlideTitle.render(slide, data.get("title", "Protecting the Federal Balance"))

        # Left: 3 Stacked Amendment Steps
        steps = data.get("steps", [
            {"title": "Step 1: Parliament Consent", "body": "Must be passed by at least two-thirds majority in both Houses."},
            {"title": "Step 2: State Ratification", "body": "Must be ratified by the legislatures of at least half of the total states."},
            {"title": "Step 3: Judicial Scrutiny", "body": "The Supreme Court checks that basic constitutional structures remain inviolate."}
        ])[:3]

        y_coords = [2.05, 3.45, 4.85]
        for i, st in enumerate(steps):
            InfoCard.render(slide, 0.70, y_coords[i], 5.80, 1.25,
                            title=st.get("title"), body=st.get("body"),
                            ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                            default_index=i)

        # Right: Large Dark Explanation Panel
        dark_p = data.get("dark_panel", {
            "title": "The Judiciary as Umpire",
            "body": "The Supreme Court and High Courts hold constitutional authority to oversee power disputes between Union and States, preventing executive overreach."
        })
        DarkCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                        title=dark_p.get("title"), body=dark_p.get("body"),
                        icon_color=COLORS.rgb_accent_orange, default_index=3)

        SlideFooter.render(slide, data.get("page_num", 12), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F13: Dark Section Transition
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f13(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide, with_abstract_circles=True)

        SlideKicker.render(slide, data.get("kicker", "FROM PROVISIONS TO PRACTICE"), is_dark=True, x=0.90, y=1.10)

        title = data.get("title", "How Is Federalism Practised?")
        tb_t = add_text_box(slide, 0.85, 1.45, 11.50, 1.00)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = str(title).strip()
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(40.0)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_white

        intro = data.get("lead", "Constitutional provisions are necessary, but not sufficient. The real success of federalism in India is attributed to the nature of democratic politics.")
        tb_i = add_text_box(slide, 0.90, 2.55, 10.80, 0.80)
        p_i = tb_i.text_frame.paragraphs[0]
        p_i.text = str(intro).strip()
        p_i.font.name = FONTS.body
        p_i.font.size = Pt(15.5)
        p_i.font.color.rgb = COLORS.rgb_text_on_dark
        p_i.line_spacing = 1.15

        # 3 Outlined Dark Cards Below
        cards = data.get("cards", [
            {"title": "Linguistic States", "body": "Creation of states along language lines strengthened national unity."},
            {"title": "Language Policy", "body": "Flexibility and safeguards for non-Hindi languages prevented friction."},
            {"title": "Centre-State Relations", "body": "Rise of regional parties and coalition eras fostered genuine autonomy."}
        ])[:3]

        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 2.70
        for i, c in enumerate(cards):
            DarkCard.render(slide, x_coords[i], 3.70, w, h,
                            title=c.get("title"), body=c.get("body"),
                            ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                            default_index=i)

    # ──────────────────────────────────────────────────────────────────────────
    # F14: Large Image + Three Insights
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f14(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "REDRAWING THE POLITICAL MAP"))
        SlideTitle.render(slide, data.get("title", "India in 1947 and After"))

        # Left Large Framed Map
        map_img = images.get("image-14-1.png") or images.get("map_bytes") or images.get("image_id")
        MapFrame.render(slide, 0.70, 2.05, 6.80, 4.60,
                        map_bytes=map_img, caption="Redrawing of state boundaries along linguistic and cultural criteria.")

        # Right 3 Stacked Insights
        insights = data.get("insights", [
            {"title": "Boundaries Redrawn", "body": "Old provincial boundaries vanished to ensure people speaking the same language lived together."},
            {"title": "Cultural Recognition", "body": "States like Nagaland, Uttarakhand, and Jharkhand were formed for culture and geography."},
            {"title": "Democratic Stability", "body": "Contrary to initial fears of fragmentation, linguistic federalism unified the republic."}
        ])[:3]

        y_coords = [2.05, 3.55, 5.05]
        for i, ins in enumerate(insights):
            card_func = CreamCard.render if i == 1 else InfoCard.render
            card_func(slide, 7.80, y_coords[i], 4.80, 1.35,
                      title=ins.get("title"), body=ins.get("body"),
                      icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 14), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F15: Argument + Image + Quote
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f15(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE FIRST MAJOR TEST"))
        SlideTitle.render(slide, data.get("title", "Linguistic States"))

        # Left Column: Arguments + Quote
        thesis = data.get("thesis", "When the demand for the formation of states on the basis of language was raised, some national leaders feared it would lead to the disintegration of the country.")
        InfoCard.render(slide, 0.70, 2.05, 6.40, 2.10,
                        title="Initial Fears vs Historical Reality", body=thesis,
                        icon_color=COLORS.rgb_primary_teal, default_index=0)

        quote = data.get("quote", "Experience has shown that the formation of linguistic states has actually made the country more united and administration easier.")
        EditorialQuoteCard.render(slide, 0.70, 4.35, 6.40, 2.30,
                                  quote_text=quote, attribution=data.get("attribution", "National Commission Report"))

        # Right Column: Historical Photo
        photo = images.get("image-15-1.png") or images.get("image_id")
        ImageFrame.render(slide, 7.40, 2.05, 5.20, 4.60,
                          img_bytes=photo, caption="Historical debates over the reorganization of Indian states.", fit_mode="COVER")

        SlideFooter.render(slide, data.get("page_num", 15), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F16: 2x2 Concept Grid + Insight Strip
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f16(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE SECOND TEST"))
        SlideTitle.render(slide, data.get("title", "Language Policy of the Indian Union"))

        cards = data.get("cards", [
            {"title": "No National Language", "body": "The Constitution did not give the status of national language to any one language."},
            {"title": "Hindi as Official", "body": "Hindi was identified as the official language, spoken by roughly 40-44% of citizens."},
            {"title": "21 Scheduled Languages", "body": "Besides Hindi, 21 other languages are recognized in the Eighth Schedule."},
            {"title": "English Continuation", "body": "Flexibility allowed English to continue alongside Hindi for official purposes."}
        ])[:4]

        x_coords = [0.70, 6.80]
        y_coords = [2.05, 3.85]
        w, h = 5.80, 1.65

        for i, c in enumerate(cards):
            col = i % 2
            row = i // 2
            card_func = CreamCard.render if i == 2 else InfoCard.render
            card_func(slide, x_coords[col], y_coords[row], w, h,
                      title=c.get("title"), body=c.get("body"),
                      icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        # Full Width Bottom Insight Strip
        strip_text = data.get("insight", "The flexibility shown by Indian political leaders helped our country avoid the kind of language-based conflict that Sri Lanka experienced.")
        DarkCard.render(slide, 0.70, 5.65, 11.90, 1.00,
                        title="Key Insight", body=strip_text,
                        icon_color=COLORS.rgb_accent_orange, default_index=4)

        SlideFooter.render(slide, data.get("page_num", 16), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F17: Chart / Data Snapshot + Vertical KPI Stack
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f17(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CENSUS OF INDIA, 2011"))
        SlideTitle.render(slide, data.get("title", "India's Linguistic Diversity"))

        # Left Data Visualization Panel (Chart or Structured Overview)
        chart_summary = data.get("chart_summary", "Census 2011 recorded over 1,300 distinct mother tongues. When grouped under major language headers, 22 Scheduled Languages emerge, creating a multilingual federation where no single linguistic group constitutes an absolute majority.")
        InfoCard.render(slide, 0.70, 2.05, 6.80, 4.60,
                        title="Linguistic Structure (Census 2011)", body=chart_summary,
                        icon_color=COLORS.rgb_primary_teal, default_index=0)

        # Right KPI Stack
        MetricCard.render(slide, 7.80, 2.05, 4.80, 1.35,
                          value=data.get("kpi1_val", "1,300+"),
                          label=data.get("kpi1_lbl", "Mother Tongues"),
                          subtext="Recorded across rural and urban districts.")

        MetricCard.render(slide, 7.80, 3.55, 4.80, 1.35,
                          value=data.get("kpi2_val", "43.6%"),
                          label=data.get("kpi2_lbl", "Hindi Native Speakers"),
                          subtext="The single largest linguistic group.",
                          is_cream=True)

        MetricCard.render(slide, 7.80, 5.05, 4.80, 1.35,
                          value=data.get("kpi3_val", "22"),
                          label=data.get("kpi3_lbl", "Scheduled Languages"),
                          subtext="Guaranteed equal dignity in the Eighth Schedule.")

        SlideFooter.render(slide, data.get("page_num", 17), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F18: Before / After + Dual Images
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f18(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE THIRD WAY FEDERALISM STRENGTHENED"))
        SlideTitle.render(slide, data.get("title", "Centre-State Relations: Before & After 1990"))

        # Left Column: Before & After Cards
        c_before = data.get("before", {
            "title": "Before 1990: One-Party Dominance",
            "body": "One national party ruled both at the centre and in most states. Central governments frequently misused constitutional provisions to dismiss state governments."
        })
        NegativeCard.render(slide, 0.70, 2.05, 5.80, 2.15,
                            title=c_before.get("title"), body=c_before.get("body"), default_index=0)

        c_after = data.get("after", {
            "title": "After 1990: Era of Coalition Politics",
            "body": "Rise of regional parties in multiple states meant major national parties formed coalitions, leading to genuine respect for state autonomy."
        })
        InfoCard.render(slide, 0.70, 4.45, 5.80, 2.20,
                        title=c_after.get("title"), body=c_after.get("body"),
                        icon_color=COLORS.rgb_primary_teal, default_index=1)

        # Right Column: Maps / Visuals
        img_top = images.get("image-18-3.png") or images.get("image_top")
        img_bot = images.get("image-18-4.png") or images.get("image_bot")
        MapFrame.render(slide, 6.80, 2.05, 5.80, 2.15, map_bytes=img_top, caption="Pre-1990: Dominant national rule")
        MapFrame.render(slide, 6.80, 4.45, 5.80, 2.20, map_bytes=img_bot, caption="Post-1990: Diverse multi-party coalition landscape")

        SlideFooter.render(slide, data.get("page_num", 18), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F19: Definition + Four Reasons
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f19(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE RATIONALE FOR A THIRD TIER"))
        SlideTitle.render(slide, data.get("title", "Decentralisation in India"))

        # Top Definition Banner
        def_text = data.get("definition", "Decentralisation means taking power away from central and state governments and delegating it to local municipal and panchayat bodies.")
        DarkCard.render(slide, 0.70, 2.05, 11.90, 1.05,
                        title="Core Definition", body=def_text,
                        icon_color=COLORS.rgb_accent_orange, default_index=0)

        # Bottom 4 Concept Columns
        reasons = data.get("reasons", [
            {"title": "Local Knowledge", "body": "Local people have better knowledge of neighbourhood problems and spending priorities."},
            {"title": "Direct Management", "body": "People understand how to manage money and run local services efficiently."},
            {"title": "Direct Participation", "body": "Citizens participate directly in decision-making at the village or ward level."},
            {"title": "Democratic Habit", "body": "Instills the everyday habit of self-governance and accountability."}
        ])[:4]

        x_coords = [0.70, 3.77, 6.84, 9.91]
        w, h = 2.72, 3.35
        for i, r in enumerate(reasons):
            card_func = CreamCard.render if i % 2 == 1 else InfoCard.render
            card_func(slide, x_coords[i], 3.30, w, h,
                      title=r.get("title"), body=r.get("body"),
                      ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 19), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F20: Six Feature / Reform Grid (2x3 Grid)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f20(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "A MAJOR STEP IN 1992"))
        SlideTitle.render(slide, data.get("title", "Strengthening the Third Tier"))

        reforms = data.get("reforms", [
            {"title": "Mandatory Elections", "body": "Constitutionally mandatory to hold regular elections to local government bodies."},
            {"title": "Reserved Seats", "body": "Seats reserved in elected bodies and executive heads for SC, ST, and OBC communities."},
            {"title": "One-Third Women", "body": "At least one-third of all elected posts reserved exclusively for women leaders."},
            {"title": "State Election Commission", "body": "Independent commission created in each state to conduct panchayat elections."},
            {"title": "Revenue Sharing", "body": "State governments must share genuine revenue and fiscal resources with local bodies."},
            {"title": "Real Power Transfer", "body": "Constitutional amendment transferred subjects from state control to local jurisdiction."}
        ])[:6]

        x_coords = [0.70, 4.77, 8.84]
        y_coords = [2.05, 4.35]
        w, h = 3.79, 2.15

        for i, r in enumerate(reforms):
            col = i % 3
            row = i // 3
            InfoCard.render(slide, x_coords[col], y_coords[row], w, h,
                            title=r.get("title"), body=r.get("body"),
                            ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                            default_index=i)

        SlideFooter.render(slide, data.get("page_num", 20), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F21: Split Hierarchy (Rural vs Urban Local Government)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f21(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "HOW LOCAL GOVERNMENT IS ORGANISED"))
        SlideTitle.render(slide, data.get("title", "The Structure of Local Government"))

        # Left Panel (Rural: Panchayati Raj)
        rural_body = data.get("rural", "• Gram Panchayat: Village council headed by the Sarpanch.\n• Panchayat Samiti: Block-level body of representative panchayats.\n• Zilla Parishad: District-level council headed by the Zilla Chairperson.")
        InfoCard.render(slide, 0.70, 2.05, 5.80, 4.60,
                        title="Rural  |  Panchayati Raj", body=rural_body,
                        icon_color=COLORS.rgb_primary_teal, default_index=0)

        # Right Panel (Urban: Municipal Bodies)
        urban_body = data.get("urban", "• Municipalities: Set up in towns, controlled by elected municipal councils.\n• Municipal Corporations: Constituted for big metropolitan cities.\n• Mayor: Political head of the Municipal Corporation.")
        CreamCard.render(slide, 6.80, 2.05, 5.80, 4.60,
                         title="Urban  |  Municipal Bodies", body=urban_body,
                         icon_color=COLORS.rgb_accent_orange, default_index=1)

        SlideFooter.render(slide, data.get("page_num", 21), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F22: Impact / Gains / Challenges
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f22(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE LARGEST EXPERIMENT IN DEMOCRACY"))
        SlideTitle.render(slide, data.get("title", "Local Government: Impact and Challenges"))

        # Standardized 3-Column Grid
        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 4.60

        # Left Hero Metric Card
        MetricCard.render(slide, x_coords[0], 2.05, w, h,
                          value=data.get("hero_val", "36 Lakh"),
                          label="Elected Representatives",
                          subtext="The largest democratic representative exercise in human history, including over 10 lakh women elected leaders across India.")

        # Middle Column: Gains
        gains = data.get("gains", "• Deepened democracy at the absolute grassroots level.\n• Substantially increased women's political representation.\n• Elevated local community voice in daily administration.\n• Direct accountability for local basic infrastructure.")
        InfoCard.render(slide, x_coords[1], 2.05, w, h,
                        title="Historic Gains", body=gains,
                        icon_color=COLORS.rgb_primary_teal, default_index=0)

        # Right Column: Challenges
        challenges = data.get("challenges", "• Gram Sabha meetings are still not held regularly in many states.\n• Most state governments have not transferred significant fiscal powers.\n• Local bodies remain resource-starved without independent revenue.\n• Administrative autonomy remains incomplete.")
        NegativeCard.render(slide, x_coords[2], 2.05, w, h,
                            title="Ongoing Challenges", body=challenges,
                            default_index=1)

        SlideFooter.render(slide, data.get("page_num", 22), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F23: Four-Takeaway Summary (2x2 Grid)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f23(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "IN SUMMARY"))
        SlideTitle.render(slide, data.get("title", "Key Takeaways"))

        takeaways = data.get("takeaways", [
            {"title": "Unity with Diversity", "body": "Federal power-sharing combines national integrity with regional cultural diversity."},
            {"title": "Asymmetric Balance", "body": "Flexibility in lists, special provisions, and language policies preserves harmony."},
            {"title": "Constitutional Safeguards", "body": "Bilateral consent and independent judicial review guard the federal compact."},
            {"title": "Deepened Democracy", "body": "The 1992 constitutional amendment transformed grassroots local governance."}
        ])[:4]

        x_coords = [0.70, 6.80]
        y_coords = [2.05, 4.35]
        w, h = 5.80, 2.15

        for i, t in enumerate(takeaways):
            col = i % 2
            row = i // 2
            card_func = CreamCard.render if i % 2 == 1 else InfoCard.render
            card_func(slide, x_coords[col], y_coords[row], w, h,
                      title=t.get("title"), body=t.get("body"),
                      ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 23), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F24: Dark Closing Slide
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f24(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide, with_abstract_circles=True)

        title = data.get("title", "Federalism")
        tb_t = add_text_box(slide, 0.90, 2.40, 11.50, 1.20)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = str(title).strip()
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(56.0)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_white

        statement = data.get("statement", "Unity with diversity, power shared across three tiers of governance.")
        tb_s = add_text_box(slide, 0.95, 3.75, 11.00, 0.70)
        p_s = tb_s.text_frame.paragraphs[0]
        p_s.text = str(statement).strip()
        p_s.font.name = FONTS.body
        p_s.font.size = Pt(20.0)
        p_s.font.color.rgb = COLORS.rgb_text_on_dark

        quote = data.get("quote", "Far from undermining Indian unity, linguistic states and federal decentralisation have established a resilient democratic foundation.")
        tb_q = add_text_box(slide, 1.35, 4.90, 10.60, 0.70)
        p_q = tb_q.text_frame.paragraphs[0]
        p_q.text = f"“{quote.strip()}”"
        p_q.font.name = FONTS.display
        p_q.font.size = Pt(15.0)
        p_q.font.italic = True
        p_q.font.color.rgb = COLORS.rgb_accent_orange

        meta = data.get("footer", "DeckPilot AI  |  Federalism Editorial Presentation")
        tb_m = add_text_box(slide, 1.35, 5.75, 10.60, 0.35)
        p_m = tb_m.text_frame.paragraphs[0]
        p_m.text = str(meta).strip()
        p_m.font.name = FONTS.body
        p_m.font.size = Pt(11.0)
        p_m.font.color.rgb = COLORS.rgb_text_on_dark

    # ──────────────────────────────────────────────────────────────────────────
    # F25: Horizontal Timeline (Chronological Milestones)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f25(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CHRONOLOGICAL TIMELINE"))
        SlideTitle.render(slide, data.get("title", data.get("heading", "Historical Evolution")))

        milestones = data.get("milestones") or data.get("items") or [
            {"year": "1947", "title": "Independence", "body": "Colonial provinces and 500+ princely states integrate."},
            {"year": "1950", "title": "Constitution", "body": "Republic proclaimed with Union and State legislative lists."},
            {"year": "1956", "title": "Linguistic States", "body": "States Reorganisation Act reshapes boundaries on language."},
            {"year": "1992", "title": "Decentralisation", "body": "73rd and 74th Amendments establish local Panchayats and Cities."}
        ]
        milestones = milestones[:4]

        # Horizontal connecting track line
        TimelineTrack.render(slide, 1.20, 3.40, 11.80, 3.40, width_pt=2.5)

        x_coords = [0.70, 3.77, 6.84, 9.91]
        w, h = 2.72, 2.70

        for i, m in enumerate(milestones):
            node_x = x_coords[i] + (w / 2.0) - 0.18
            TimelineNode.render(slide, node_x, 3.22, diameter=0.36, is_highlight=(i == len(milestones) - 1))

            # Year badge
            yr_str = str(m.get("year", f"Step {i+1}"))
            Pill.render(slide, node_x - 0.40, 2.65, yr_str, variant="orange" if i == len(milestones) - 1 else "teal", height=0.34)

            # Card below
            card_func = CreamCard.render if i % 2 == 1 else InfoCard.render
            card_func(slide, x_coords[i], 3.80, w, h,
                      title=m.get("title"), body=m.get("body"),
                      icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 25), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F26: Vertical Timeline
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f26(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "SEQUENCE & TIMELINE"))
        SlideTitle.render(slide, data.get("title", data.get("heading", "Chronological Progression")))

        events = data.get("events") or data.get("items") or [
            {"year": "Phase 1: 1947–1965", "title": "Consolidation & Linguistic States", "body": "Establishing state boundaries along linguistic lines to ensure unity."},
            {"year": "Phase 2: 1965–1990", "title": "Centralised Dominance & Friction", "body": "Frequent dismissals of state assemblies under single-party rule."},
            {"year": "Phase 3: 1990–Present", "title": "Coalition Federalism & Devolution", "body": "Regional empowerment and the constitutional third tier of local democracy."}
        ]
        events = events[:3]

        # Vertical track line
        TimelineTrack.render(slide, 2.50, 2.20, 2.50, 6.20, width_pt=2.5)

        y_coords = [2.05, 3.55, 5.05]
        h = 1.35
        for i, ev in enumerate(events):
            TimelineNode.render(slide, 2.32, y_coords[i] + 0.50, diameter=0.36, is_highlight=(i == 2))

            # Date pill left
            Pill.render(slide, 0.70, y_coords[i] + 0.50, ev.get("year", f"Era {i+1}"), variant="teal" if i < 2 else "orange", height=0.34)

            # Card right
            card_func = CreamCard.render if i == 1 else InfoCard.render
            card_func(slide, 3.20, y_coords[i], 9.40, h,
                      title=ev.get("title"), body=ev.get("body"),
                      icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 26), deck_title=data.get("deck_title", "Federalism"))

    # ──────────────────────────────────────────────────────────────────────────
    # F27: Era / Phase Timeline
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_f27(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "HISTORICAL ERAS"))
        SlideTitle.render(slide, data.get("title", data.get("heading", "Three Eras of Federal Governance")))

        eras = data.get("eras") or data.get("items") or [
            {"era": "ERA 1 (1950–1967)", "title": "One-Party Consensus", "body": "Single-party command at centre and states, disputes settled internally."},
            {"era": "ERA 2 (1967–1989)", "title": "Confrontation & Friction", "body": "Regional parties rise; central executive uses Article 356 dismissals."},
            {"era": "ERA 3 (1989–Present)", "title": "Multiparty Coalition", "body": "No single national party rules alone; state parties become kingmakers."}
        ]
        eras = eras[:3]

        x_coords = [0.70, 4.77, 8.84]
        w, h = 3.79, 4.60
        for i, er in enumerate(eras):
            card_func = CreamCard.render if i == 1 else InfoCard.render
            card_func(slide, x_coords[i], 2.05, w, h,
                      title=f"{er.get('era')}\n{er.get('title')}", body=er.get("body"),
                      ghost_no=str(i + 1), icon_color=COLORS.rgb_primary_teal if i % 2 == 0 else COLORS.rgb_accent_orange,
                      default_index=i)

        SlideFooter.render(slide, data.get("page_num", 27), deck_title=data.get("deck_title", "Federalism"))
