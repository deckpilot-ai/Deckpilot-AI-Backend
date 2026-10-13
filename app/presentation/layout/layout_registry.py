"""Layout Registry for the Presentation Design System.

Defines all supported layout archetypes with semantic metadata, content constraints,
and asset requirements for explainable layout scoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class LayoutMetadata:
    id: str
    family: str
    name: str
    description: str
    is_dark: bool = False
    min_items: int = 0
    max_items: int = 12
    requires_image: bool = False
    supports_table: bool = False
    supports_chart: bool = False
    supports_quote: bool = False
    supports_stats: bool = False
    supports_timeline: bool = False
    supports_process: bool = False
    scoring_hints: List[str] = field(default_factory=list)


LAYOUT_REGISTRY: Dict[str, LayoutMetadata] = {
    "L01": LayoutMetadata(
        id="L01", family="cover", name="Cover / Title Hero",
        description="Opening title slide with dark canvas and right framed artwork",
        is_dark=True, requires_image=True, min_items=1, max_items=1,
        scoring_hints=["cover", "opening", "title", "hero"]
    ),
    "L02": LayoutMetadata(
        id="L02", family="agenda", name="Chapter / Agenda Map",
        description="2x3 card grid with icon circles, ghost numbers, and headers",
        is_dark=False, min_items=4, max_items=6,
        scoring_hints=["agenda", "roadmap", "outline", "table_of_contents", "chapter_map"]
    ),
    "L03": LayoutMetadata(
        id="L03", family="concept", name="Concept + Question Box + Image",
        description="Editorial prose on left, cream reflection callout below, photo on right",
        is_dark=False, requires_image=True, supports_quote=True,
        scoring_hints=["concept", "definition", "question", "big_idea", "reflection"]
    ),
    "L04": LayoutMetadata(
        id="L04", family="table_data", name="Table + Image + Insight",
        description="Structured table on left, image upper-right, insight card lower-right",
        is_dark=False, supports_table=True, requires_image=True, supports_quote=True,
        scoring_hints=["table", "matrix", "breakdown", "categories"]
    ),
    "L05": LayoutMetadata(
        id="L05", family="comparison", name="Two Concept Cards + Image + Strip",
        description="Two stacked concept cards on left, image right, full-width dark takeaway strip",
        is_dark=False, requires_image=True, min_items=2, max_items=2,
        scoring_hints=["conflict", "tradeoff", "two_concepts", "dual_perspective"]
    ),
    "L06": LayoutMetadata(
        id="L06", family="concept_grid", name="Four Concept Grid + Quote + Image",
        description="2x2 cards left, image top-right, cream quote card bottom-right",
        is_dark=False, requires_image=True, supports_quote=True, min_items=3, max_items=4,
        scoring_hints=["four_pillars", "dimensions", "aspects", "quadrant"]
    ),
    "L07": LayoutMetadata(
        id="L07", family="comparison", name="Three Comparison Rows",
        description="Three horizontal comparison rows with labels and explanation, image right",
        is_dark=False, requires_image=True, min_items=3, max_items=3,
        scoring_hints=["comparison_rows", "alternatives", "options", "choices"]
    ),
    "L08": LayoutMetadata(
        id="L08", family="question_cards", name="Three Icon Question Cards + Image",
        description="3 stacked cards with circular icons on left, vertical photo on right",
        is_dark=False, requires_image=True, min_items=3, max_items=3,
        scoring_hints=["questions", "inquiry", "perspectives", "pillars"]
    ),
    "L09": LayoutMetadata(
        id="L09", family="process", name="Three-Step Process",
        description="3 horizontal cards with step numbers, arrows, and dark formula strip below",
        is_dark=False, min_items=3, max_items=3, supports_process=True,
        scoring_hints=["process", "steps", "workflow", "methodology", "formula"]
    ),
    "L10": LayoutMetadata(
        id="L10", family="kpi", name="KPI / Stat Trio",
        description="Three large metric cards with Cambria 34pt values and descriptions",
        is_dark=False, supports_stats=True, min_items=3, max_items=3,
        scoring_hints=["statistics", "kpi", "numbers", "thresholds", "tiers"]
    ),
    "L11": LayoutMetadata(
        id="L11", family="chart", name="Chart + Visual Comparison",
        description="Clustered column chart left, dual comparison cards right",
        is_dark=False, supports_chart=True,
        scoring_hints=["chart", "distribution", "inequality", "bar_comparison"]
    ),
    "L12": LayoutMetadata(
        id="L12", family="chart_table", name="Chart + Table + Question Callout",
        description="Column chart left, table top-right, cream insight box bottom-right",
        is_dark=False, supports_chart=True, supports_table=True, supports_quote=True,
        scoring_hints=["chart_and_table", "state_metrics", "multi_indicator"]
    ),
    "L13": LayoutMetadata(
        id="L13", family="chart_image", name="Chart + Image + Dark Insight",
        description="Column chart left, image top-right, dark takeaway card bottom-right",
        is_dark=False, supports_chart=True, requires_image=True,
        scoring_hints=["chart_with_photo", "trend_insight", "takeaway_chart"]
    ),
    "L14": LayoutMetadata(
        id="L14", family="rows", name="Three Concept Rows + Image + Note",
        description="Three stacked concept rows left, photo top-right, cream callout bottom-right",
        is_dark=False, requires_image=True, supports_quote=True, min_items=3, max_items=3,
        scoring_hints=["public_goods", "facilities", "services", "amenities"]
    ),
    "L15": LayoutMetadata(
        id="L15", family="table_evidence", name="Table + Multi-Image Evidence",
        description="Data table left, two stacked photos right, dark takeaway strip below",
        is_dark=False, supports_table=True, requires_image=True,
        scoring_hints=["table_evidence", "case_data", "dual_photo"]
    ),
    "L16": LayoutMetadata(
        id="L16", family="framework", name="Three-Pillar Framework",
        description="Three centered pillar cards with icon badges, vertical photo on right",
        is_dark=False, requires_image=True, min_items=3, max_items=3,
        scoring_hints=["framework", "three_pillars", "dimensions", "core_pillars"]
    ),
    "L17": LayoutMetadata(
        id="L17", family="chart_table", name="Comparative Bar Chart + Table",
        description="Horizontal bar chart left, compact comparison table right",
        is_dark=False, supports_chart=True, supports_table=True,
        scoring_hints=["rank_comparison", "country_ranking", "cross_entity"]
    ),
    "L18": LayoutMetadata(
        id="L18", family="section_opener", name="Dark Section Opener",
        description="Dark canvas, intro lead, 2 dark cards left, large cream quote right",
        is_dark=True, supports_quote=True, min_items=2, max_items=2,
        scoring_hints=["section_transition", "chapter_opener", "dark_divider", "thematic_shift"]
    ),
    "L19": LayoutMetadata(
        id="L19", family="stat_visual", name="Stacked Statistics + Illustration",
        description="Three horizontal stat cards left with vertical hairline divider, photo right",
        is_dark=False, supports_stats=True, requires_image=True, min_items=3, max_items=3,
        scoring_hints=["horizontal_stats", "crisis_metrics", "depletion", "stat_evidence"]
    ),
    "L20": LayoutMetadata(
        id="L20", family="table_tiles", name="Data Table + Image + Two Insight Tiles",
        description="Table left, photo right, 2 contrasting insight cards at bottom",
        is_dark=False, supports_table=True, requires_image=True,
        scoring_hints=["resource_table", "projections", "two_insights"]
    ),
    "L21": LayoutMetadata(
        id="L21", family="dark_principles", name="Dark Three-Card Principle",
        description="Dark canvas, 3 horizontal cards, full-width cream quote strip bottom",
        is_dark=True, supports_quote=True, min_items=3, max_items=3,
        scoring_hints=["dark_principles", "core_tenets", "foundational_laws"]
    ),
    "L22": LayoutMetadata(
        id="L22", family="summary", name="Six Takeaway Grid",
        description="2x3 cards with icon badge, ghost sequence number, title, and body",
        is_dark=False, min_items=4, max_items=6,
        scoring_hints=["summary", "takeaways", "conclusions", "key_findings", "review"]
    ),
    "L23": LayoutMetadata(
        id="L23", family="closing", name="Closing / Reflection",
        description="Dark canvas, reflective question, short copy, framed thematic artwork right",
        is_dark=True, requires_image=True, min_items=1, max_items=1,
        scoring_hints=["closing", "reflection", "final", "future_outlook", "q_and_a"]
    ),
    "L_TIMELINE": LayoutMetadata(
        id="L_TIMELINE", family="timeline", name="Editorial Timeline Track",
        description="Horizontal chronological track with circular nodes and event callouts",
        is_dark=False, supports_timeline=True, min_items=3, max_items=5,
        scoring_hints=["timeline", "chronology", "history", "milestones", "phases"]
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # Federalism Editorial Archetypes (F01–F27)
    # ──────────────────────────────────────────────────────────────────────────
    "F01": LayoutMetadata(
        id="F01", family="cover", name="Federalism Dark Cover Hero",
        description="Dark teal canvas with abstract watermark circles, prominent title, kicker, and context badge line",
        is_dark=True, min_items=1, max_items=1,
        scoring_hints=["cover", "hero", "title", "opening"]
    ),
    "F02": LayoutMetadata(
        id="F02", family="roadmap", name="Federalism Vertical Roadmap",
        description="Vertical roadmap stack of 4-7 horizontal cards with icon badges and ghost numbers",
        is_dark=False, min_items=4, max_items=7,
        scoring_hints=["roadmap", "agenda", "outline", "stages", "table_of_contents"]
    ),
    "F03": LayoutMetadata(
        id="F03", family="framework", name="Definition + Government Levels + Principles",
        description="Deep teal definition card left, two supporting level cards right, wide principles strip below",
        is_dark=False, min_items=3, max_items=6,
        scoring_hints=["definition", "framework", "levels", "principles", "system_overview"]
    ),
    "F04": LayoutMetadata(
        id="F04", family="comparison", name="Two-System Comparison Panel",
        description="Two large side-by-side comparison cards with colored headers, icon badges, and status pills",
        is_dark=False, min_items=2, max_items=2,
        scoring_hints=["comparison", "dual", "unitary_vs_federal", "contrast", "two_systems"]
    ),
    "F05": LayoutMetadata(
        id="F05", family="metrics_map", name="Metrics + Large Map / Visual",
        description="Two metric cards and one dark insight card left, large framed map or image right",
        is_dark=False, requires_image=True, supports_stats=True,
        scoring_hints=["metrics_map", "map_statistics", "geography_stats", "global_context"]
    ),
    "F06": LayoutMetadata(
        id="F06", family="split_comparison", name="Split Comparison List",
        description="Two equal vertical panels with icon + heading and bullet check points",
        is_dark=False, min_items=2, max_items=2,
        scoring_hints=["split_list", "comparison_bullets", "two_paths", "contrasting_models"]
    ),
    "F07": LayoutMetadata(
        id="F07", family="features", name="Multi-Feature Grid",
        description="3-column grid with 6-7 numbered feature cards with teal/orange badges",
        is_dark=False, min_items=4, max_items=7,
        scoring_hints=["features", "feature_grid", "principles_grid", "key_features", "building_blocks"]
    ),
    "F08": LayoutMetadata(
        id="F08", family="categories", name="Two Large Category Cards",
        description="Two major category panels with large icons, paragraphs, insights, and example pills",
        is_dark=False, min_items=2, max_items=2,
        scoring_hints=["categories", "two_types", "routes", "dual_categories", "formation_routes"]
    ),
    "F09": LayoutMetadata(
        id="F09", family="tiers", name="Three-Tier / Three-Step System",
        description="Context strip above, three connected tier cards with sequence arrows below",
        is_dark=False, min_items=3, max_items=3, supports_process=True,
        scoring_hints=["three_tiers", "tiers", "hierarchy_tiers", "three_levels", "three_steps"]
    ),
    "F10": LayoutMetadata(
        id="F10", family="three_lists", name="Three Category Lists + Strip",
        description="Three vertical cards with colored headers, definitions, and item lists plus insight strip",
        is_dark=False, min_items=3, max_items=3,
        scoring_hints=["three_lists", "legislative_lists", "jurisdictions", "three_columns", "union_state_concurrent"]
    ),
    "F11": LayoutMetadata(
        id="F11", family="dual_detail", name="Dual Detail Panel (Teal & Cream)",
        description="Soft teal panel left, warm cream panel right, with pills and detail items",
        is_dark=False, min_items=2, max_items=2,
        scoring_hints=["dual_detail", "asymmetric_comparison", "special_provisions", "asymmetry"]
    ),
    "F12": LayoutMetadata(
        id="F12", family="process_insight", name="Step Flow + Dark Insight Panel",
        description="3 stacked numbered steps on left, large dark explanation panel on right",
        is_dark=False, min_items=3, max_items=3, supports_process=True,
        scoring_hints=["step_flow", "governance_steps", "process_insight", "judiciary_umpire"]
    ),
    "F13": LayoutMetadata(
        id="F13", family="section_opener", name="Dark Section Transition",
        description="Dark teal canvas, watermark circles, intro kicker/title, 3 dark cards below",
        is_dark=True, min_items=2, max_items=3,
        scoring_hints=["section_transition", "dark_transition", "chapter_divider", "thematic_break"]
    ),
    "F14": LayoutMetadata(
        id="F14", family="image_insights", name="Large Map + Three Insights",
        description="Large framed map/image left, three stacked insight cards right",
        is_dark=False, requires_image=True, min_items=2, max_items=3,
        scoring_hints=["map_insights", "image_insights", "photo_stack", "state_reorganization"]
    ),
    "F15": LayoutMetadata(
        id="F15", family="argument_quote", name="Argument + Image + Quote",
        description="Strong thesis + 3 checks + quote block left, large photo right",
        is_dark=False, requires_image=True, supports_quote=True,
        scoring_hints=["argument", "thesis_quote", "evidence_quote", "editorial_defense"]
    ),
    "F16": LayoutMetadata(
        id="F16", family="concept_grid", name="2x2 Concept Grid + Insight Strip",
        description="Four concept cards with icon badges, full-width warm cream insight strip below",
        is_dark=False, min_items=4, max_items=4,
        scoring_hints=["four_concepts", "language_grid", "2x2_grid", "quadrant", "multilingual"]
    ),
    "F17": LayoutMetadata(
        id="F17", family="chart_kpis", name="Chart + Vertical KPI Stack",
        description="Clustered column/bar chart left, 4 vertical KPI cards right with semantic colors",
        is_dark=False, supports_chart=True, supports_stats=True, min_items=3, max_items=4,
        scoring_hints=["chart_kpis", "data_stack", "chart_metrics", "census_data"]
    ),
    "F18": LayoutMetadata(
        id="F18", family="before_after", name="Before / After + Dual Images",
        description="Before card and After card left, 2 supporting comparison images right",
        is_dark=False, requires_image=True, min_items=2, max_items=2,
        scoring_hints=["before_after", "transformation", "dual_maps", "era_shift"]
    ),
    "F19": LayoutMetadata(
        id="F19", family="definition_reasons", name="Definition + Four Reasons",
        description="Top full-width definition panel, four concept columns with icons below",
        is_dark=False, min_items=3, max_items=4,
        scoring_hints=["definition_reasons", "four_pillars", "decentralisation_reasons", "rationale"]
    ),
    "F20": LayoutMetadata(
        id="F20", family="reforms_grid", name="Six Reform / Feature Grid",
        description="Intro statement above, 2x3 light feature cards with icon badges below",
        is_dark=False, min_items=4, max_items=6,
        scoring_hints=["reforms", "amendments", "policy_grid", "six_reforms", "1992_amendments"]
    ),
    "F21": LayoutMetadata(
        id="F21", family="hierarchy", name="Split Hierarchy (Rural vs Urban)",
        description="Two major columns with nested hierarchical levels, connectors, and badges",
        is_dark=False, min_items=2, max_items=4,
        scoring_hints=["hierarchy", "rural_urban", "governance_structure", "org_tree", "panchayat_municipality"]
    ),
    "F22": LayoutMetadata(
        id="F22", family="impact_cases", name="Impact / Gains / Challenges / Cases",
        description="Hero metric top left, gains & challenges columns, two case-study cards below",
        is_dark=False, supports_stats=True, min_items=2, max_items=4,
        scoring_hints=["impact", "gains_challenges", "case_studies", "evaluations", "ground_realities"]
    ),
    "F23": LayoutMetadata(
        id="F23", family="summary", name="Four-Takeaway Summary",
        description="2x2 summary grid with ghost numbers, icon badges, and key conclusions",
        is_dark=False, min_items=3, max_items=4,
        scoring_hints=["summary", "takeaways", "conclusions", "four_takeaways", "final_wrap"]
    ),
    "F24": LayoutMetadata(
        id="F24", family="closing", name="Dark Closing Slide",
        description="Dark teal canvas, large closing statement, supporting line, minimal and elegant",
        is_dark=True, min_items=1, max_items=1,
        scoring_hints=["closing", "final", "conclusion", "closing_hero", "reflection"]
    ),
    "F25": LayoutMetadata(
        id="F25", family="timeline", name="Federalism Horizontal Timeline",
        description="Horizontal chronological track with nodes, milestone pills, and alternating cards",
        is_dark=False, supports_timeline=True, min_items=3, max_items=5,
        scoring_hints=["timeline", "horizontal_timeline", "milestones", "chronology", "history"]
    ),
    "F26": LayoutMetadata(
        id="F26", family="timeline", name="Federalism Vertical Timeline",
        description="Vertical track with date pills left, milestone nodes, and explanation cards right",
        is_dark=False, supports_timeline=True, min_items=3, max_items=4,
        scoring_hints=["vertical_timeline", "roadmap_timeline", "sequence", "progression"]
    ),
    "F27": LayoutMetadata(
        id="F27", family="timeline", name="Federalism Era / Phase Timeline",
        description="Three large vertical era cards with ghost numbers, titles, and structural analysis",
        is_dark=False, supports_timeline=True, min_items=3, max_items=3,
        scoring_hints=["era_timeline", "phases", "historical_eras", "three_eras", "regime_shifts"]
    ),
}

