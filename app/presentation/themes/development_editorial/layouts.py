"""Layout Composers for the Development Editorial Theme.

Implements all 23 extracted archetypes (L01 through L23) plus L_TIMELINE.
Maintains exact editorial geometry, cards, image frames, tables, and typography.
"""

import logging
from typing import Any, Dict, List, Optional

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from app.presentation.themes.development_editorial.tokens import COLORS, FONTS, SPACING
from app.presentation.themes.development_editorial.typography import format_kicker_text, normalize_title
from app.presentation.themes.development_editorial.components import (
    DarkInfoCard, EditorialDivider, GhostNumber, HorizontalMetricCard, IconBadge,
    ImageFrame, InfoCard, MetricCard, QuoteCard, SlideKicker, SlideSubtitle,
    SlideTitle, StyledTable, SummaryStrip, add_text_box, create_solid_shape
)

logger = logging.getLogger(__name__)


def _set_dark_background(slide: Any):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = COLORS.rgb_canvas_dark


def _set_light_background(slide: Any):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = COLORS.rgb_canvas


class LayoutComposers:
    """Registry of concrete slide composers for L01 - L23 + Timeline."""

    # ──────────────────────────────────────────────────────────────────────────
    # L01: Cover Hero (Dark)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l01(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide)
        raw_title = data.get("title", "Development")
        title, extra_sub = normalize_title(raw_title, max_words=4)
        kicker = data.get("kicker", "CLASS 10 ECONOMICS")
        subtitle = data.get("subtitle") or extra_sub or "Understanding Economic Development"
        description = data.get("body", "An inquiry into aspirations, economic progress, and sustainable living.")
        img_bytes = images.get(data.get("image_id", ""))

        # 1. Kicker
        SlideKicker.render(slide, kicker, is_dark=True, y=1.20)

        # 2. Hero Title (Cambria, dynamically budgeted to prevent overlap)
        title_len = len(title)
        font_size = 48.0 if title_len <= 16 else (36.0 if title_len <= 35 else 30.0)
        title_h = 1.00 if title_len <= 16 else (1.50 if title_len <= 35 else 1.90)

        tb_t = add_text_box(slide, 0.60, 1.70, 6.50, title_h)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = title
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(font_size)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_white

        # 3. Subtitle & Description (placed safely below title)
        sub_y = max(3.40, 1.70 + title_h + 0.25)
        sub_h = max(1.10, 5.50 - sub_y)
        tb_b = add_text_box(slide, 0.60, sub_y, 6.40, sub_h)
        p_s = tb_b.text_frame.paragraphs[0]
        p_s.text = subtitle
        p_s.font.name = FONTS.display
        p_s.font.size = Pt(17.0)
        p_s.font.bold = True
        p_s.font.color.rgb = COLORS.rgb_gold_light

        p_d = tb_b.text_frame.add_paragraph()
        p_d.text = description
        p_d.font.name = FONTS.body
        p_d.font.size = Pt(13.5)
        p_d.font.color.rgb = COLORS.rgb_text_on_dark
        p_d.space_before = Pt(6)

        # 4. Mustard Divider
        EditorialDivider.render(slide, 0.60, 5.70, 3.50, color=COLORS.rgb_gold)

        # 5. Small Footer
        tb_f = add_text_box(slide, 0.60, 5.90, 6.40, 0.35)
        p_f = tb_f.text_frame.paragraphs[0]
        p_f.text = f"{kicker} | {subtitle}"
        p_f.font.name = FONTS.body
        p_f.font.size = Pt(11.0)
        p_f.font.color.rgb = COLORS.rgb_text_footer_dark

        # 6. Framed Artwork on Right
        ImageFrame.render(slide, 7.30, 1.70, 5.40, 4.30, image_bytes=img_bytes, warm_card=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L02: Chapter / Agenda Map (Light, 2x3 cards)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l02(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CHAPTER MAP"))
        SlideTitle.render(slide, data.get("title", "What This Chapter Explores"))
        SlideSubtitle.render(slide, data.get("lead", "Development has many aspects: from individual aspirations to national metrics and sustainability."), y=1.55)

        items = data.get("items", [])[:6]
        x_coords = [0.60, 4.69, 8.78]
        y_coords = [2.40, 4.70]
        w, h = 3.93, 2.15

        for idx in range(6):
            col = idx % 3
            row = idx // 3
            x = x_coords[col]
            y = y_coords[row]
            item = items[idx] if idx < len(items) else {"title": f"Topic {idx+1}", "body": "Overview of foundational themes."}
            icon_col = COLORS.rgb_green_primary if (idx % 2 == 0) else COLORS.rgb_gold
            
            InfoCard.render(slide, x, y, w, h,
                            title=item.get("title"),
                            body=item.get("body"),
                            ghost_no=str(idx + 1),
                            icon_color=icon_col)

    # ──────────────────────────────────────────────────────────────────────────
    # L03: Concept + Question Box + Image
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l03(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE BIG IDEA"))
        SlideTitle.render(slide, data.get("title", "The Idea of Development"))

        # Left prose
        tb = add_text_box(slide, 0.60, 1.75, 7.60, 2.40)
        p = tb.text_frame.paragraphs[0]
        p.text = data.get("body", "The idea of progress has always been with us. We have aspirations about how we want to live and what a nation should be like. Development means thinking through these questions and how to reach them.")
        p.font.name = FONTS.body
        p.font.size = Pt(16.0)
        p.font.color.rgb = COLORS.rgb_ink
        p.line_spacing = 1.20

        # Bottom cream question card
        question = data.get("quote", data.get("question", "Can we have development without destroying collective well-being?"))
        QuoteCard.render(slide, 0.60, 4.40, 7.60, 2.30, question, attribution=data.get("attribution", "Key Reflection"))

        # Right framed photo
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.55, 1.75, 4.15, 4.95, image_bytes=img_bytes, caption=data.get("image_caption", "The human aspiration for progress"))

    # ──────────────────────────────────────────────────────────────────────────
    # L04: Table + Image + Insight
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l04(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.1"))
        SlideTitle.render(slide, data.get("title", "Different People, Different Goals"))
        SlideSubtitle.render(slide, data.get("lead", "Each person seeks what fulfils their own aspirations."), y=1.65, w=7.60)

        # Left Table
        headers = data.get("table_headers", ["Category of Person", "Developmental Goals"])
        rows = data.get("table_rows", [
            ["Landless rural labourers", "More days of work and better wages; quality local schooling."],
            ["Prosperous farmers", "High family income through higher support prices for crops."],
            ["Urban unemployed youth", "Stable employment opportunities and job security."],
            ["A girl from a rich urban family", "She gets as much freedom as her brother and decides her path."]
        ])
        StyledTable.render(slide, 0.60, 2.50, 7.60, 3.80, headers, rows)

        # Top-right Image
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.55, 1.85, 4.15, 2.70, image_bytes=img_bytes)

        # Bottom-right Insight Card
        insight = data.get("insight", "Conflicting Goals: What is development for one may be destructive for another.")
        QuoteCard.render(slide, 8.55, 4.85, 4.15, 1.80, insight, strong_border=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L05: Two Concept Cards + Image + Summary Strip
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l05(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "WHEN PRIORITIES COLLIDE"))
        SlideTitle.render(slide, data.get("title", "When Goals Conflict"))

        items = data.get("items", [
            {"title": "Freedom and Opportunity", "body": "A woman expects the same freedom and respect as her brothers, while they may prefer traditional expectations."},
            {"title": "Industrial Growth vs Land", "body": "Industrialists want more dams for cheap electricity, but submerging land disrupts tribal communities."}
        ])
        
        # 2 stacked cards on left
        InfoCard.render(slide, 0.60, 1.85, 7.40, 1.80, title=items[0].get("title"), body=items[0].get("body"), icon_color=COLORS.rgb_green_primary)
        InfoCard.render(slide, 0.60, 3.80, 7.40, 1.80, title=items[1].get("title"), body=items[1].get("body"), icon_color=COLORS.rgb_gold)

        # Image right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.35, 1.85, 4.35, 3.75, image_bytes=img_bytes)

        # Bottom summary strip
        strip_text = data.get("summary", "Two things are clear: different persons can have different developmental goals, and what is development for one may be destructive for another.")
        SummaryStrip.render(slide, 0.60, 5.80, 12.10, 1.05, "Key Principle", strip_text)

    # ──────────────────────────────────────────────────────────────────────────
    # L06: Four Concept Grid + Quote + Image
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l06(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "BEYOND THE PAY CHEQUE"))
        SlideTitle.render(slide, data.get("title", "Income and Other Goals"))

        items = data.get("items", [
            {"title": "Equal Treatment", "body": "People resent discrimination and value dignity above financial gains."},
            {"title": "Freedom", "body": "Autonomy to make life decisions and choose careers without coercion."},
            {"title": "Security", "body": "Predictable employment, personal safety, and social welfare protection."},
            {"title": "Respect of Others", "body": "Dignity in the workplace and community validation of worth."}
        ])[:4]

        # 2x2 grid left (width = 7.40 in)
        x_left = [0.60, 4.35]
        y_top = [1.85, 4.30]
        w, h = 3.60, 2.30

        for i, item in enumerate(items):
            xi = x_left[i % 2]
            yi = y_top[i // 2]
            col = COLORS.rgb_green_primary if i % 2 == 0 else COLORS.rgb_gold
            InfoCard.render(slide, xi, yi, w, h, title=item.get("title"), body=item.get("body"), icon_color=col)

        # Image top-right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.30, 1.85, 4.40, 2.30, image_bytes=img_bytes)

        # Cream Quote Card bottom-right
        quote = data.get("quote", "Money in your pocket cannot buy a pollution-free environment or protect you from disease.")
        QuoteCard.render(slide, 8.30, 4.30, 4.40, 2.30, quote, attribution=data.get("attribution", "Economic Insight"))

    # ──────────────────────────────────────────────────────────────────────────
    # L07: Three Comparison Rows + Image + Summary Callout
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l07(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "A MIX OF GOALS"))
        SlideTitle.render(slide, data.get("title", "Comparing Employment Choices"))
        SlideSubtitle.render(slide, data.get("lead", "When considering employment, people weigh more than just immediate pay cheques."), y=1.65, w=8.40)

        rows = data.get("rows", [
            {"label": "Job A: High Pay", "body": "Pays well, but offers no job security and leaves no time for family. This reduces your sense of freedom and security."},
            {"label": "Job B: Lower Pay", "body": "Offers regular employment and enhances your sense of security over the long run."},
            {"label": "Job C: Safe Environment", "body": "If women are engaged in paid work, their dignity in household and society increases."}
        ])[:3]

        y_starts = [2.50, 3.85, 5.20]
        for idx, row in enumerate(rows):
            y = y_starts[idx]
            InfoCard.render(slide, 0.60, y, 8.40, 1.15, title=row.get("label"), body=row.get("body"))

        # Image right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 9.30, 1.95, 3.40, 2.50, image_bytes=img_bytes)

        # Dark summary bottom-right
        SummaryStrip.render(slide, 9.30, 4.80, 3.40, 1.95, "Takeaway", data.get("summary", "Development involves a mix of goals: income, security, and personal dignity."))

    # ──────────────────────────────────────────────────────────────────────────
    # L08: Three Icon Question Cards + Image
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l08(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "FROM PERSONS TO NATIONS"))
        SlideTitle.render(slide, data.get("title", "National Development"))
        SlideSubtitle.render(slide, data.get("lead", "If individuals seek different goals, their notion of national development will differ too."), y=1.65, w=7.60)

        questions = data.get("items", [
            {"title": "Whom does it serve?", "body": "Can all citizens benefit equally, or does one group prosper at another's expense?"},
            {"title": "Is there a better way?", "body": "Could the same progress be achieved with fewer displacements and ecological harm?"},
            {"title": "What constitutes fair?", "body": "National development means finding answers that are fair and just for all people."}
        ])[:3]

        y_positions = [2.65, 4.00, 5.35]
        for i, q in enumerate(questions):
            col = COLORS.rgb_green_primary if i % 2 == 0 else COLORS.rgb_gold
            InfoCard.render(slide, 0.60, y_positions[i], 7.60, 1.20, title=q.get("title"), body=q.get("body"), icon_color=col)

        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.55, 1.95, 4.15, 4.90, image_bytes=img_bytes)

    # ──────────────────────────────────────────────────────────────────────────
    # L09: Three-Step Process
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l09(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CHOOSING A YARDSTICK"))
        SlideTitle.render(slide, data.get("title", "How Do We Compare Countries?"))
        SlideSubtitle.render(slide, data.get("lead", "Comparing nations requires choosing indicators tailored to the purpose of comparison."), y=1.65)

        steps = data.get("steps", [
            {"title": "Total Income", "body": "Total national earnings provide an aggregate baseline, but ignore total population size."},
            {"title": "Per Capita Income", "body": "Divide national income by population to find average earnings per citizen."},
            {"title": "PPP Normalization", "body": "Convert to Purchasing Power Parity (US$) so currency values reflect actual domestic purchasing power."}
        ])[:3]

        x_coords = [0.60, 4.80, 9.00]
        w, h = 3.93, 2.50
        for i, st in enumerate(steps):
            col = COLORS.rgb_green_primary if i == 0 else (COLORS.rgb_gold if i == 1 else COLORS.rgb_green_mid)
            InfoCard.render(slide, x_coords[i], 2.80, w, h, title=f"Step {i+1}: {st.get('title')}", body=st.get("body"), icon_color=col)

        # Full-width dark formula strip
        formula = data.get("formula", "Per Capita Income = (Total National Income) / (Total National Population)")
        SummaryStrip.render(slide, 0.60, 5.65, 12.10, 1.10, "Formula", formula)

    # ──────────────────────────────────────────────────────────────────────────
    # L10: KPI / Stat Trio
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l10(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "WORLD BANK, 2024"))
        SlideTitle.render(slide, data.get("title", "Classifying Countries by Income"))
        SlideSubtitle.render(slide, data.get("lead", "In its World Development Reports, the World Bank categorizes nations by per capita income thresholds."), y=1.65)

        stats = data.get("stats", [
            {"val": "US$ 66,500", "label": "High Income", "desc": "Countries above this threshold are classified as high-income nations."},
            {"val": "US$ 3,250", "label": "India (Middle)", "desc": "India sits in the low-middle income category as of recent reporting.", "warning": True},
            {"val": "US$ 1,400", "label": "Low Income", "desc": "Countries with per capita earnings below this baseline are low-income."}
        ])[:3]

        x_coords = [0.60, 4.80, 9.00]
        w, h = 3.93, 2.70
        for i, s in enumerate(stats):
            is_warn = s.get("warning", False) or (i == 1)
            MetricCard.render(slide, x_coords[i], 2.65, w, h, s.get("val"), s.get("label"), s.get("desc"), is_warning=is_warn)

        SlideSubtitle.render(slide, data.get("note", "Source: World Development Indicators, World Bank. High-income countries excluding Middle East oil nations are termed developed nations."), is_dark=False, y=5.60, h=0.60)

    # ──────────────────────────────────────────────────────────────────────────
    # L11: Chart + Visual Comparison
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l11(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.2"))
        SlideTitle.render(slide, data.get("title", "Averages Can Hide Disparities"))
        SlideSubtitle.render(slide, data.get("lead", "Two nations can report identical average incomes, yet reflect vastly unequal societies."), y=1.65, w=7.20)

        # Clustered column chart left
        chart_data = CategoryChartData()
        chart_data.categories = ["Citizen 1", "Citizen 2", "Citizen 3", "Citizen 4", "Citizen 5"]
        chart_data.add_series("Country A (Equitable)", (9500, 10500, 9800, 10000, 10200))
        chart_data.add_series("Country B (Disparity)", (500, 500, 500, 500, 48000))

        chart_shape = slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.60), Inches(2.55), Inches(7.20), Inches(4.10), chart_data
        )
        chart = chart_shape.chart
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False

        # 2 comparison cards on right
        InfoCard.render(slide, 8.10, 2.55, 4.60, 1.85, title="Country A: Broad Wellbeing", body="Equitably distributed income where citizens enjoy shared middle-class purchasing power.")
        QuoteCard.render(slide, 8.10, 4.65, 4.60, 2.00, "In Country B, 1 citizen holds 96% of the wealth while 4 citizens live in deep poverty.", attribution="Inequality Diagnostic", strong_border=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L12: Chart + Table + Question Callout
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l12(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.3"))
        SlideTitle.render(slide, data.get("title", "Per Capita Income of Three States"))
        SlideSubtitle.render(slide, data.get("lead", "Income alone suggests Haryana leads, but human indicators challenge this picture."), y=1.65, w=7.20)

        # Chart on Left
        chart_data = CategoryChartData()
        chart_data.categories = ["Haryana", "Kerala", "Bihar"]
        chart_data.add_series("Per Capita Income (Rs)", (264000, 230000, 46000))
        chart_shape = slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.60), Inches(2.50), Inches(7.20), Inches(4.10), chart_data
        )

        # Table upper-right
        headers = ["State", "PC Income (Rs)"]
        rows = [["Haryana", "2,64,000"], ["Kerala", "2,30,000"], ["Bihar", "46,000"]]
        StyledTable.render(slide, 8.10, 2.50, 4.60, 2.00, headers, rows)

        # Cream Question lower-right
        q = data.get("question", "Does the richest state provide the best healthcare, schooling, and public security?")
        QuoteCard.render(slide, 8.10, 4.80, 4.60, 1.80, q, strong_border=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L13: Chart + Image + Dark Insight
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l13(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.4"))
        SlideTitle.render(slide, data.get("title", "Money Is Not the Whole Story"))
        SlideSubtitle.render(slide, data.get("lead", "Comparing health and schooling indicators alongside financial earnings."), y=1.65, w=7.50)

        # Chart on Left
        chart_data = CategoryChartData()
        chart_data.categories = ["Haryana", "Kerala", "Bihar"]
        chart_data.add_series("Infant Mortality Rate", (30, 7, 32))
        chart_data.add_series("Literacy Rate (%)", (82, 94, 62))
        slide.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.60), Inches(2.50), Inches(7.50), Inches(4.10), chart_data
        )

        # Image top-right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.40, 2.50, 4.30, 2.30, image_bytes=img_bytes)

        # Dark insight bottom-right
        SummaryStrip.render(slide, 8.40, 5.00, 4.30, 1.60, "Vital Fact", "Kerala's infant mortality rate is one-fourth of Haryana's despite lower state GDP.")

    # ──────────────────────────────────────────────────────────────────────────
    # L14: Three Concept Rows + Image + Note
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l14(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "WHY FACILITIES MATTER"))
        SlideTitle.render(slide, data.get("title", "Public Facilities and Well-Being"))
        SlideSubtitle.render(slide, data.get("lead", "For many essential services, the cheapest and most effective path is collective provision."), y=1.65, w=7.60)

        rows = data.get("items", [
            {"title": "Community Security", "body": "It is cheaper and safer to provide collective security for a neighborhood than for each home to hire a private guard."},
            {"title": "Public Education", "body": "Children study effectively when communities establish accessible public schools for all children."},
            {"title": "Disease Prevention", "body": "Infectious illnesses are contained only when public sanitation and clean water are provided collectively."}
        ])[:3]

        y_coords = [2.50, 3.85, 5.20]
        for i, r in enumerate(rows):
            col = COLORS.rgb_green_primary if i % 2 == 0 else COLORS.rgb_gold
            InfoCard.render(slide, 0.60, y_coords[i], 7.60, 1.15, title=r.get("title"), body=r.get("body"), icon_color=col)

        # Image top-right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.50, 2.00, 4.20, 2.70, image_bytes=img_bytes)

        # Cream note lower-right
        QuoteCard.render(slide, 8.50, 4.90, 4.20, 1.70, "Collective provision guarantees baseline dignity regardless of individual income.")

    # ──────────────────────────────────────────────────────────────────────────
    # L15: Table + Multi-Image Evidence
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l15(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.5"))
        SlideTitle.render(slide, data.get("title", "Why Some States Do Better"))
        SlideSubtitle.render(slide, data.get("lead", "Public distribution systems and primary schooling create persistent social resilience."), y=1.65, w=7.60)

        # Table left
        headers = ["State", "Rural Literacy", "PDS Function"]
        rows = [["Kerala", "94%", "Well-managed"], ["Haryana", "82%", "Moderate"], ["Bihar", "62%", "Distressed"]]
        StyledTable.render(slide, 0.60, 2.50, 7.60, 2.60, headers, rows)

        # Bottom-left dark takeaway
        SummaryStrip.render(slide, 0.60, 5.40, 7.60, 1.25, "Key Finding", "Where the Public Distribution System (PDS) functions well, nutritional and health status is significantly superior.")

        # 2 stacked images right
        img_bytes1 = images.get(data.get("image_id_1", ""))
        img_bytes2 = images.get(data.get("image_id_2", ""))
        ImageFrame.render(slide, 8.55, 2.00, 4.15, 2.30, image_bytes=img_bytes1)
        ImageFrame.render(slide, 8.55, 4.55, 4.15, 2.10, image_bytes=img_bytes2)

    # ──────────────────────────────────────────────────────────────────────────
    # L16: Three-Pillar Framework
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l16(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "UNDP"))
        SlideTitle.render(slide, data.get("title", "The Human Development Report"))
        SlideSubtitle.render(slide, data.get("lead", "HDI evaluates development across three foundational pillars rather than income alone."), y=1.65, w=8.20)

        pillars = data.get("pillars", [
            {"title": "Health & Longevity", "body": "Life expectancy at birth measures disease prevention and community health."},
            {"title": "Educational Attainment", "body": "Mean years of schooling and expected schooling evaluate intellectual capability."},
            {"title": "Decent Standard of Living", "body": "Per Capita GNI in Purchasing Power Parity measures material enablement."}
        ])[:3]

        x_coords = [0.60, 3.40, 6.20]
        w, h = 2.60, 2.70
        for i, p in enumerate(pillars):
            col = COLORS.rgb_green_primary if i == 0 else (COLORS.rgb_gold if i == 1 else COLORS.rgb_green_mid)
            InfoCard.render(slide, x_coords[i], 2.80, w, h, title=p.get("title"), body=p.get("body"), icon_color=col)

        # Framed book/report image on right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 9.20, 2.00, 3.50, 4.60, image_bytes=img_bytes, caption="Human Development Report")

        # Bottom synthesis
        SlideSubtitle.render(slide, "HDI ranks 190+ countries, proving high income does not automatically yield human flourishing.", is_dark=False, y=5.85, h=0.60)

    # ──────────────────────────────────────────────────────────────────────────
    # L17: Comparative Bar Chart + Table
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l17(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "TABLE 1.6"))
        SlideTitle.render(slide, data.get("title", "India and Its Neighbours"))
        SlideSubtitle.render(slide, data.get("lead", "Comparing HDI ranks and per capita gross national income in South Asia."), y=1.65, w=7.40)

        # Bar chart on Left
        chart_data = CategoryChartData()
        chart_data.categories = ["Sri Lanka", "India", "Bangladesh", "Pakistan", "Nepal"]
        chart_data.add_series("Life Expectancy (Years)", (76.4, 67.2, 72.4, 66.1, 68.4))
        slide.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED,
            Inches(0.60), Inches(2.50), Inches(7.40), Inches(4.10), chart_data
        )

        # Compact comparison table on Right
        headers = ["Country", "GNI (US$)", "HDI Rank"]
        rows = [
            ["Sri Lanka", "12,578", "73"],
            ["India", "6,590", "132"],
            ["Bangladesh", "4,976", "129"],
            ["Pakistan", "4,624", "161"],
            ["Nepal", "3,877", "143"]
        ]
        StyledTable.render(slide, 8.35, 2.50, 4.35, 3.40, headers, rows)

        SlideSubtitle.render(slide, "Sri Lanka, despite its smaller size, ranks far ahead of India on life expectancy and HDI.", is_dark=False, x=8.35, y=6.00, w=4.35, h=0.60)

    # ──────────────────────────────────────────────────────────────────────────
    # L18: Dark Section Opener
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l18(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide)
        SlideKicker.render(slide, data.get("kicker", "LOOKING AHEAD"), is_dark=True)
        SlideTitle.render(slide, data.get("title", "The Sustainability of Development"), is_dark=True)
        SlideSubtitle.render(slide, data.get("lead", "We have not inherited the world from our forefathers; we have borrowed it from our children."), is_dark=True, y=1.75, w=7.40)

        # 2 dark cards left
        items = data.get("items") or data.get("cards") or [
            {"title": "Renewable Depletion", "body": "Groundwater reserves in Punjab and western UP are receding at alarming rates due to agricultural over-extraction."},
            {"title": "Non-Renewable Exhaustion", "body": "Global crude oil reserves will exhaust in approximately 50 years at current extraction trajectories."}
        ]
        item1 = items[0] if len(items) > 0 else {}
        item2 = items[1] if len(items) > 1 else {}

        DarkInfoCard.render(slide, 0.60, 2.80, 7.40, 1.85,
                           title=item1.get("title", "Resource Tension"),
                           body=item1.get("body", "Long-term sustainability dictates balance between extraction and replenishment."),
                           icon_color=COLORS.rgb_green_mid)

        DarkInfoCard.render(slide, 0.60, 4.90, 7.40, 1.85,
                           title=item2.get("title", "Systemic Challenge"),
                           body=item2.get("body", "Transition timelines must reconcile physical infrastructure constraints with rising consumption."),
                           icon_color=COLORS.rgb_gold)

        # Large cream quote right
        quote = data.get("quote", "Economic growth that destroys ecological foundations is not development; it is self-inflicted impoverishment.")
        QuoteCard.render(slide, 8.40, 2.20, 4.30, 4.55, quote, attribution=data.get("attribution", "World Commission on Environment"))

    # ──────────────────────────────────────────────────────────────────────────
    # L19: Stacked Statistics + Illustration
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l19(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "EXAMPLE 1, RENEWABLE"))
        SlideTitle.render(slide, data.get("title", "Groundwater Under Threat"))
        SlideSubtitle.render(slide, data.get("lead", "Recent evidence suggests that groundwater across India is under severe depletion threat."), y=1.65, w=7.60)

        stats = data.get("stats", [
            {"val": "300+", "label": "Districts Overusing", "desc": "Reporting water level decline of over 4 meters in the last 20 years."},
            {"val": "33%", "label": "National Reserve", "desc": "One-third of the country is presently overusing groundwater reserves."},
            {"val": "60%", "label": "Projected Crisis", "desc": "Could be overusing reserves within 25 years if current practices persist.", "warn": True}
        ])[:3]

        y_starts = [2.50, 3.95, 5.40]
        for i, s in enumerate(stats):
            HorizontalMetricCard.render(slide, 0.60, y_starts[i], 7.60, 1.25, s.get("val"), s.get("label"), s.get("desc"), is_warning=s.get("warn", False))

        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.55, 1.95, 4.15, 4.90, image_bytes=img_bytes)

    # ──────────────────────────────────────────────────────────────────────────
    # L20: Data Table + Image + Two Insight Tiles
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l20(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "EXAMPLE 2, NON-RENEWABLE"))
        SlideTitle.render(slide, data.get("title", "Crude Oil Will Run Out"))
        SlideSubtitle.render(slide, data.get("lead", "Crude oil reserves are finite. Present extraction rates dictate limited lifespan."), y=1.65, w=7.60)

        # Table left
        headers = ["Region", "Reserves (Billion Barrels)", "Years of Reserve"]
        rows = [
            ["Middle East", "803", "70 Years"],
            ["United States", "50", "11 Years"],
            ["World Total", "1,733", "50 Years"]
        ]
        StyledTable.render(slide, 0.60, 2.50, 7.60, 2.60, headers, rows)

        # Two contrasting cards bottom-left
        SummaryStrip.render(slide, 0.60, 5.35, 3.65, 1.30, "Import Risk", "India imports 85% of crude; rising prices drain fiscal budgets.")
        QuoteCard.render(slide, 4.55, 5.35, 3.65, 1.30, "A country with military power can secure oil, but cannot prevent exhaustion.", strong_border=False)

        # Image right
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 8.55, 1.95, 4.15, 4.90, image_bytes=img_bytes)

    # ──────────────────────────────────────────────────────────────────────────
    # L21: Dark Three-Card Principle Slide
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l21(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE SHARED CHALLENGE"), is_dark=True)
        SlideTitle.render(slide, data.get("title", "Why Sustainability Matters"), is_dark=True)

        cards = data.get("cards", [
            {"title": "Global Interlinkage", "body": "Environmental degradation no longer respects national borders. Our future is inextricably shared."},
            {"title": "Multidisciplinary", "body": "Scientists, economists, and philosophers collaborate to redefine development within planetary limits."},
            {"title": "Ethical Stewardship", "body": "Progress demands continuous public debate about where we want to go and what kind of society we desire."}
        ])[:3]

        x_coords = [0.60, 4.80, 9.00]
        w, h = 3.93, 2.65
        for i, c in enumerate(cards):
            DarkInfoCard.render(slide, x_coords[i], 2.10, w, h, title=c.get("title"), body=c.get("body"), icon_color=COLORS.rgb_green_mid)

        # Full width cream quote strip below
        quote = data.get("quote", "The Earth provides enough to satisfy every man's needs, but not every man's greed.")
        QuoteCard.render(slide, 0.60, 5.05, 12.10, 1.70, quote, attribution="Mahatma Gandhi", strong_border=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L22: Six Takeaway Grid
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l22(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "IN SUMMARY"))
        SlideTitle.render(slide, data.get("title", "Key Takeaways"))

        takeaways = data.get("items", [
            {"title": "Development is Plural", "body": "Different people hold different, sometimes conflicting, aspirations for progress."},
            {"title": "Income is Not Enough", "body": "People equally value freedom, security, fair treatment, and social dignity."},
            {"title": "Averages Can Mislead", "body": "Per capita metrics hide extreme disparities in wealth and living standards."},
            {"title": "Public Goods Count", "body": "Collective health, schooling, and sanitation determine genuine flourishing."},
            {"title": "Human Development", "body": "The UNDP HDI framework proves human capability surpasses GDP."},
            {"title": "Make It Last", "body": "True development must sustain ecological resources for future generations."}
        ])[:6]

        x_coords = [0.60, 4.69, 8.78]
        y_coords = [1.85, 4.35]
        w, h = 3.93, 2.30

        for i in range(6):
            col = i % 3
            row = i // 3
            item = takeaways[i] if i < len(takeaways) else {"title": f"Takeaway {i+1}", "body": "Core summary insight."}
            icon_col = COLORS.rgb_green_primary if (i % 2 == 0) else COLORS.rgb_gold
            InfoCard.render(slide, x_coords[col], y_coords[row], w, h,
                            title=item.get("title"), body=item.get("body"),
                            ghost_no=str(i + 1), icon_color=icon_col)

    # ──────────────────────────────────────────────────────────────────────────
    # L23: Closing / Reflection
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_l23(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_dark_background(slide)
        SlideKicker.render(slide, data.get("kicker", "THE DEBATE CONTINUES"), is_dark=True, y=2.00)

        # Reflective Title
        raw_title = data.get("title", "The Road Ahead")
        clean_title, _ = normalize_title(raw_title, max_words=4)
        tb_t = add_text_box(slide, 0.60, 2.50, 6.40, 1.50)
        p_t = tb_t.text_frame.paragraphs[0]
        p_t.text = clean_title
        p_t.font.name = FONTS.display
        p_t.font.size = Pt(40.0)
        p_t.font.bold = True
        p_t.font.color.rgb = COLORS.rgb_white

        # Description
        tb_d = add_text_box(slide, 0.60, 4.10, 6.30, 1.40)
        p_d = tb_d.text_frame.paragraphs[0]
        p_d.text = data.get("body", "At all times, as members of society and as individuals, we keep asking what we want to become and what our goals are. The debate about development never ends.")
        p_d.font.name = FONTS.body
        p_d.font.size = Pt(15.5)
        p_d.font.color.rgb = COLORS.rgb_text_on_dark_muted
        p_d.line_spacing = 1.20

        # Mustard line
        EditorialDivider.render(slide, 0.60, 5.65, 3.00, color=COLORS.rgb_gold)

        # Footer
        tb_f = add_text_box(slide, 0.60, 5.85, 6.40, 0.40)
        p_f = tb_f.text_frame.paragraphs[0]
        p_f.text = data.get("footer", "Development Studies | Understanding Economic Development")
        p_f.font.name = FONTS.body
        p_f.font.size = Pt(12.5)
        p_f.font.color.rgb = COLORS.rgb_text_footer_dark

        # Thematic right image
        img_bytes = images.get(data.get("image_id", ""))
        ImageFrame.render(slide, 7.30, 2.30, 5.40, 3.40, image_bytes=img_bytes, warm_card=True)

    # ──────────────────────────────────────────────────────────────────────────
    # L_TIMELINE: Editorial Chronology Track
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def render_timeline(cls, slide: Any, data: Dict[str, Any], images: Dict[str, bytes]):
        _set_light_background(slide)
        SlideKicker.render(slide, data.get("kicker", "CHRONOLOGY"))
        SlideTitle.render(slide, data.get("title", "Evolution and Key Milestones"))
        SlideSubtitle.render(slide, data.get("lead", "Tracing chronological development and policy transformations over time."), y=1.65)

        events = data.get("events", [
            {"date": "Phase 1", "title": "Foundation", "desc": "Initial framework and baseline metrics established."},
            {"date": "Phase 2", "title": "Expansion", "desc": "Broadened scope to encompass multi-dimensional public goods."},
            {"date": "Phase 3", "title": "Modern Era", "desc": "Global harmonization under unified capability metrics."},
            {"date": "Phase 4", "title": "Future Outlook", "desc": "Ecological boundaries integrated into continuous evaluation."}
        ])[:4]

        # Horizontal connecting line
        EditorialDivider.render(slide, 1.20, 3.00, 10.80, color=COLORS.rgb_green_primary)

        x_coords = [0.60, 3.70, 6.80, 9.90]
        w = 2.80
        for i, ev in enumerate(events):
            x = x_coords[i]
            # Circle node on line
            node = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + (w/2.0) - 0.20), Inches(2.80), Inches(0.40), Inches(0.40))
            node.fill.solid()
            node.fill.fore_color.rgb = COLORS.rgb_gold if i % 2 == 1 else COLORS.rgb_green_primary
            node.line.fill.background()

            # Date pill above node
            tb_d = add_text_box(slide, x, 2.35, w, 0.35)
            p_d = tb_d.text_frame.paragraphs[0]
            p_d.alignment = PP_ALIGN.CENTER
            p_d.text = ev.get("date", f"Phase {i+1}").upper()
            p_d.font.name = FONTS.body
            p_d.font.size = Pt(12.0)
            p_d.font.bold = True
            p_d.font.color.rgb = COLORS.rgb_gold

            # Event Card below node
            InfoCard.render(slide, x, 3.45, w, 2.80, title=ev.get("title"), body=ev.get("desc"))
