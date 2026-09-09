"""Presentation skill registry and domain knowledge rules."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PresentationSkill:
    name: str
    description: str
    target_audiences: list[str]
    narrative_rules: list[str]
    visual_principles: list[str]
    recommended_layouts: list[str]
    chart_recommendations: list[str]
    color_palette_hint: tuple[str, str, str]  # (primary, accent, neutral)
    title_font_hint: str
    body_font_hint: str
    qa_checklist: list[str]


SKILL_CATALOG: dict[str, PresentationSkill] = {
    "executive_presentation": PresentationSkill(
        name="executive_presentation",
        description="Boardroom and senior leadership decks emphasizing strategic takeaway headlines, concise proof points, and KPI summaries.",
        target_audiences=["Board of Directors", "C-Suite Executives", "Steering Committees"],
        narrative_rules=[
            "Use Barbara Minto Pyramid Principle: Lead with the bottom-line takeaway on slide 1.",
            "Slide titles must state the strategic insight, not a category name.",
            "Maximum 3-4 high-impact bullets per slide.",
            "Include an explicit takeaway summary callout on every core slide.",
        ],
        visual_principles=[
            "Restrained corporate palette (Deep Navy, Slate, crisp white).",
            "High contrast and generous whitespace for effortless scanning.",
            "Big number KPI callouts for core financial and operational metrics.",
        ],
        recommended_layouts=["hero", "big_numbers", "two_column", "comparison", "roadmap", "closing"],
        chart_recommendations=["column", "bar", "line", "donut"],
        color_palette_hint=("#0F172A", "#2563EB", "#EEF2F8"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Every slide has an action headline", "No wall-of-text bullets", "All numbers have provenance"],
    ),
    "consulting_deck": PresentationSkill(
        name="consulting_deck",
        description="Structured, hypothesis-driven consulting presentations with rigorous comparative analysis, frameworks, and data backing.",
        target_audiences=["Client Leadership", "Strategy Teams", "Enterprise Stakeholders"],
        narrative_rules=[
            "Situation -> Complication -> Strategic Implication structure.",
            "Rigorous MECE (Mutually Exclusive, Collectively Exhaustive) structuring.",
            "Action titles summarizing the data proof points.",
        ],
        visual_principles=[
            "Structured comparison cards and quadrant matrices.",
            "Clean grid alignment with distinct card headers.",
            "Balanced information density with clear visual hierarchy.",
        ],
        recommended_layouts=["comparison", "matrix_quadrant", "process_steps", "card_grid", "two_column", "closing"],
        chart_recommendations=["waterfall", "stacked_bar", "stacked_column", "scatter"],
        color_palette_hint=("#132A52", "#0284C7", "#F0F4F8"),
        title_font_hint="Calibri",
        body_font_hint="Calibri",
        qa_checklist=["Hypothesis clearly stated", "Comparisons use parallel structure", "Frameworks have labels"],
    ),
    "technical_presentation": PresentationSkill(
        name="technical_presentation",
        description="Engineering, cloud architecture, and AI infrastructure decks featuring system diagrams, flow pipelines, and technical capability maps.",
        target_audiences=["Chief Technology Officers", "Engineers", "Architects", "Technical Evaluators"],
        narrative_rules=[
            "Problem in current architecture -> Solution architecture -> Capabilities & Benchmarks -> Deployment Roadmap.",
            "Avoid generic marketing fluff; focus on performance, scalability, security, and latency.",
        ],
        visual_principles=[
            "Modern technical aesthetic: Deep Charcoal/Indigo with Electric Blue or Cyan accents.",
            "Hub-and-spoke and linear sequence connectors.",
            "Capability matrices with clear category groupings.",
        ],
        recommended_layouts=["architecture_diagram", "process_steps", "two_column", "card_grid", "matrix_quadrant", "timeline"],
        chart_recommendations=["line", "column", "bar", "area"],
        color_palette_hint=("#18181B", "#06B6D4", "#F4F4F5"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Architecture flow is clear", "Technical terms spelled correctly", "Deployment sequence is logical"],
    ),
    "pitch_deck": PresentationSkill(
        name="pitch_deck",
        description="Venture capital and investor pitch presentations designed to communicate huge market opportunity, unique moat, traction, and unit economics.",
        target_audiences=["Venture Capitalists", "Angel Investors", "Investment Committees"],
        narrative_rules=[
            "Problem -> Solution -> Market Size (TAM/SAM/SOM) -> Product & Moat -> Traction -> Business Model -> Team -> The Ask.",
            "Compelling narrative momentum on every slide.",
        ],
        visual_principles=[
            "High visual energy, bold contrasting hero elements.",
            "Big growth charts and standout traction metrics.",
            "Visual product highlights and clean customer logos/proof.",
        ],
        recommended_layouts=["hero", "big_numbers", "chart_insight", "two_column", "card_grid", "closing"],
        chart_recommendations=["line", "column", "area", "donut"],
        color_palette_hint=("#1E1B4B", "#6366F1", "#EEF2FF"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Market size clearly quantified", "Traction growth rate visible", "The Ask and use of funds clear"],
    ),
    "financial_presentation": PresentationSkill(
        name="financial_presentation",
        description="Earnings reviews, financial audits, budget allocations, and M&A decks with exact numeric provenance and native charts.",
        target_audiences=["CFOs", "Financial Analysts", "Investors", "Audit Committees"],
        narrative_rules=[
            "Financial Highlights -> Revenue Drivers -> Margin Evolution -> Cash Flow & Balance Sheet -> Guidance.",
            "Every metric must have explicit units and provenance.",
        ],
        visual_principles=[
            "Precision data styling, clean tables with zebra striping and right-aligned numbers.",
            "Uncluttered native bar, column, and waterfall charts.",
            "Subdued corporate colors (Navy, Forest Green for positive delta).",
        ],
        recommended_layouts=["table_focus", "chart_focus", "metrics_grid", "two_column", "closing"],
        chart_recommendations=["waterfall", "column", "stacked_column", "line", "bar"],
        color_palette_hint=("#0F2922", "#059669", "#F0FDF4"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["All numbers cross-check", "Units and currency symbols specified", "Tables formatted correctly"],
    ),
    "research_education": PresentationSkill(
        name="research_education",
        description="Educational lectures, textbook chapter syntheses, historical narratives, and academic research presentations.",
        target_audiences=["Students", "Researchers", "Domain Specialists", "Educators"],
        narrative_rules=[
            "Foundational context -> Core concepts & mechanisms -> Evidence & Artifacts -> Chronological evolution -> Synthesis & Open questions.",
            "Preserve domain authenticity and factual grounding.",
        ],
        visual_principles=[
            "Warm editorial feel with illustrated source figures and documentary captions.",
            "Structured chronological timelines and institutional hierarchies.",
            "Calm, readable typography with generous card containers.",
        ],
        recommended_layouts=["hero", "image_focus", "timeline", "two_column", "card_grid", "closing"],
        chart_recommendations=["bar", "column", "pie"],
        color_palette_hint=("#3D2619", "#D97706", "#FDFBF7"),
        title_font_hint="Segoe UI",
        body_font_hint="Segoe UI",
        qa_checklist=["Figures have documentary captions", "Chronology is sequential", "Synthesis concludes deck"],
    ),
}


def get_skill_for_request(topic: str, presentation_type: str = "") -> PresentationSkill:
    """Matches the most appropriate presentation skill based on topic semantics and requested type."""
    t_lower = topic.lower()
    pt_lower = presentation_type.lower()

    if "pitch" in pt_lower or "investor" in pt_lower or "seed" in t_lower or "series" in t_lower:
        return SKILL_CATALOG["pitch_deck"]
    if "tech" in pt_lower or "architecture" in pt_lower or "cloud" in t_lower or "ai" in t_lower or "software" in t_lower or "saas" in t_lower:
        return SKILL_CATALOG["technical_presentation"]
    if "finance" in pt_lower or "financial" in pt_lower or "earning" in t_lower or "budget" in t_lower or "revenue" in t_lower:
        return SKILL_CATALOG["financial_presentation"]
    if "history" in t_lower or "chapter" in t_lower or "ncert" in t_lower or "curriculum" in t_lower or "research" in pt_lower:
        return SKILL_CATALOG["research_education"]
    if "consulting" in pt_lower or "strategy" in t_lower or "assessment" in t_lower or "transformation" in t_lower:
        return SKILL_CATALOG["consulting_deck"]

    return SKILL_CATALOG["executive_presentation"]
