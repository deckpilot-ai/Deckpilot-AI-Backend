"""Presentation strategy and storyline planning agent."""

import logging
import math
import re
from typing import Any

from app.schemas.generation_state import (
    AssetMetadata,
    ChartSpec,
    ChartType,
    DiagramNode,
    DiagramSpec,
    LayoutFamily,
    PresentationGoal,
    PresentationType,
    SlideSpec,
    TableSpec,
)
from app.skills.skill_registry import get_skill_for_request

logger = logging.getLogger(__name__)


class StorylineAgent:
    """Creates presentation narrative arc, section sequence, slide specs, and layout visual rhythm."""

    @classmethod
    def create_storyline_plan(
        cls,
        goal: PresentationGoal,
        llm_plan_spec: dict[str, Any] | None = None,
        available_assets: list[AssetMetadata] | None = None,
        grounding_data: str = "",
    ) -> list[SlideSpec]:
        count = goal.target_slide_count
        assets = available_assets or []
        skill = get_skill_for_request(goal.topic, goal.presentation_type.value)

        slides_input = (llm_plan_spec or {}).get("slides", [])
        planned_specs: list[SlideSpec] = []

        # Layout rhythm tracker
        recent_layouts: list[LayoutFamily] = []

        for i in range(count):
            slide_id = f"s{i+1:02d}"
            raw_slide = slides_input[i] if i < len(slides_input) and isinstance(slides_input[i], dict) else {}

            # 1. Slide Role & Position
            is_first = (i == 0)
            is_last = (i == count - 1)

            purpose = raw_slide.get("purpose") or raw_slide.get("objective") or f"Key topic analysis for section {i+1}"
            headline = raw_slide.get("headline") or raw_slide.get("message") or f"Strategic Milestone {i+1}: Delivering Scalable Value"
            bullets = raw_slide.get("bullets") or []

            # 2. Select Layout Family with Visual Rhythm
            layout_hint = raw_slide.get("layoutHint") or raw_slide.get("layout_hint") or ""
            chosen_layout = cls._determine_layout(
                i, count, layout_hint, recent_layouts, raw_slide, assets, goal
            )
            recent_layouts.append(chosen_layout)

            # 3. Associate Visual Assets (Images / Figures)
            img_id = raw_slide.get("imageArtifactId") or raw_slide.get("image_artifact_id")
            caption = raw_slide.get("imageCaption") or raw_slide.get("image_caption") or ""

            if not img_id and assets and chosen_layout in (LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE, LayoutFamily.HERO):
                # Match closest asset
                cand_idx = i % len(assets)
                img_id = assets[cand_idx].asset_id
                caption = caption or assets[cand_idx].caption or "Documentary Reference Figure"

            # 4. Associate Charts if data / metrics present
            chart_spec = None
            if raw_slide.get("chart"):
                raw_c = raw_slide.get("chart") or {}
                c_type_str = raw_c.get("type", "column").lower()
                c_type = ChartType.COLUMN
                for ct in ChartType:
                    if ct.value == c_type_str:
                        c_type = ct
                        break
                cats = raw_c.get("categories") or ["FY22", "FY23", "FY24", "FY25 (Proj)"]
                series_data = raw_c.get("series") or [
                    {"name": "Enterprise ARR ($M)", "values": [12.4, 24.8, 48.2, 85.0]}
                ]
                chart_spec = ChartSpec(
                    chart_type=c_type,
                    title=raw_c.get("title") or "Performance & Scaling Growth Trajectory",
                    categories=cats,
                    series=series_data,
                    units=raw_c.get("units", "$M"),
                    source_provenance=raw_c.get("source", "Internal Operational Data"),
                )
            elif (chosen_layout in (LayoutFamily.CHART_FOCUS, LayoutFamily.CHART_INSIGHT)) and not raw_slide.get("metrics"):
                chart_spec = ChartSpec(
                    chart_type=ChartType.COLUMN,
                    title="Performance & Scaling Growth Trajectory",
                    categories=["FY22", "FY23", "FY24", "FY25 (Proj)"],
                    series=[{"name": "Enterprise ARR ($M)", "values": [12.4, 24.8, 48.2, 85.0]}],
                    units="$M",
                    source_provenance="Internal Operational Data",
                )

            # 5. Associate Tables if requested
            table_spec = None
            if chosen_layout == LayoutFamily.TABLE_FOCUS or raw_slide.get("table"):
                raw_t = raw_slide.get("table") or {}
                table_spec = TableSpec(
                    headers=raw_t.get("headers") or ["Strategic Pillar", "Target Benchmark", "Current Status", "Key Enabler"],
                    rows=raw_t.get("rows") or [
                        ["Platform Reliability", "99.99% Uptime", "99.98% Achieved", "Multi-region failover"],
                        ["Latency SLA", "< 25ms", "18ms Average", "Edge caching layer"],
                        ["Enterprise Security", "SOC2 Type II", "Certified", "Automated compliance monitoring"],
                        ["Unit Gross Margin", "> 75%", "78% Margin", "Optimized infrastructure routing"],
                    ],
                    title=raw_t.get("title", "Operational Benchmark Matrix"),
                )

            # 6. Associate Diagrams if process or matrix layout
            diagram_spec = None
            if chosen_layout == LayoutFamily.PROCESS_STEPS:
                diagram_spec = DiagramSpec(
                    diagram_type="process",
                    nodes=[
                        DiagramNode(label="1. Ingestion & Analysis", subtext="Multi-source document and data extraction"),
                        DiagramNode(label="2. Synthesis & Architecture", subtext="Domain-aware storyline and hierarchy generation"),
                        DiagramNode(label="3. Execution & Verification", subtext="Automated slide geometry, chart and visual QA"),
                    ]
                )
            elif chosen_layout == LayoutFamily.MATRIX_QUADRANT:
                diagram_spec = DiagramSpec(
                    diagram_type="matrix",
                    nodes=[
                        DiagramNode(label="Immediate High-ROI Wins", subtext="Core automation workflows"),
                        DiagramNode(label="Strategic Capabilities", subtext="Proprietary AI and platform tooling"),
                        DiagramNode(label="Foundational Hygiene", subtext="Data compliance and infrastructure security"),
                        DiagramNode(label="Long-Term Explorations", subtext="Emerging channel experiments"),
                    ]
                )

            # 7. Construct SlideSpec
            if raw_slide.get("eyebrow"):
                eyebrow = raw_slide.get("eyebrow")
            elif raw_slide.get("chapter"):
                eyebrow = raw_slide.get("chapter")
            elif getattr(goal, "presentation_type", None) == PresentationType.RESEARCH_EDUCATION:
                eyebrow = f"Chapter {(i // 4) + 1} · {goal.topic}"
            else:
                eyebrow = f"Section {(i // 4) + 1} · {goal.topic}"

            if raw_slide.get("takeaway"):
                takeaway = raw_slide.get("takeaway")
            elif getattr(goal, "presentation_type", None) == PresentationType.RESEARCH_EDUCATION:
                takeaway = f"Core Insight: Primary evidence and historical analysis of {headline.lower()}."
            else:
                takeaway = f"Strategic Takeaway: Actionable focus on {headline.lower()}."

            speaker_notes = raw_slide.get("speakerNotes") or raw_slide.get("speaker_notes") or f"In this slide, walk the audience through {purpose.lower()}. Emphasize key findings and historical context."

            spec = SlideSpec(
                slide_id=slide_id,
                slide_number=i + 1,
                section=eyebrow,
                slide_type="hero" if is_first else ("closing" if is_last else "content"),
                layout_family=chosen_layout,
                objective=purpose,
                key_message=headline,
                headline=headline,
                eyebrow=eyebrow,
                bullets=bullets,
                metrics=raw_slide.get("metrics", []),
                takeaway=takeaway,
                speaker_notes=speaker_notes,
                image_artifact_id=img_id,
                image_caption=caption,
                chart_spec=chart_spec,
                table_spec=table_spec,
                diagram_spec=diagram_spec,
                dark_background=(is_first and count > 1) or (is_last and count > 1) or (chosen_layout in (LayoutFamily.DARK_QUOTE, LayoutFamily.SECTION_DIVIDER)),
                layout_hint=raw_slide.get("layoutHint") or raw_slide.get("layout_hint") or chosen_layout.value,
            )
            planned_specs.append(spec)

        return planned_specs

    @classmethod
    def _determine_layout(
        cls,
        index: int,
        total_slides: int,
        hint: str,
        recent: list[LayoutFamily],
        raw_slide: dict[str, Any],
        assets: list[AssetMetadata],
        goal: PresentationGoal,
    ) -> LayoutFamily:
        # Check explicit layout hint first
        if hint:
            for lf in LayoutFamily:
                if lf.value.lower() == hint.lower() or lf.name.lower() == hint.lower():
                    return lf
            if hint.lower() in ("bar_chart", "metrics", "chart"):
                return LayoutFamily.CHART_FOCUS
            if hint.lower() in ("roadmap", "process_steps"):
                return LayoutFamily.PROCESS_STEPS

        if index == 0 and total_slides > 1:
            return LayoutFamily.HERO
        if index == total_slides - 1 and total_slides > 1:
            return LayoutFamily.CLOSING

        # Content-based layout selection
        if raw_slide.get("chart") or (goal.required_charts and index in (2, 5)):
            return LayoutFamily.CHART_FOCUS
        if raw_slide.get("table"):
            return LayoutFamily.TABLE_FOCUS
        if raw_slide.get("imageArtifactId") or (assets and index in (1, 3, 7)):
            return LayoutFamily.IMAGE_FOCUS
        if "process" in raw_slide.get("purpose", "").lower() or "step" in raw_slide.get("purpose", "").lower():
            return LayoutFamily.PROCESS_STEPS
        if "timeline" in raw_slide.get("purpose", "").lower() or "chronology" in raw_slide.get("purpose", "").lower():
            return LayoutFamily.TIMELINE
        if "matrix" in raw_slide.get("purpose", "").lower() or "quadrant" in raw_slide.get("purpose", "").lower():
            return LayoutFamily.MATRIX_QUADRANT
        if raw_slide.get("metrics") and len(raw_slide["metrics"]) >= 2:
            return LayoutFamily.METRICS_GRID

        # Alternating visual rhythm defaults
        alternator = [
            LayoutFamily.TWO_COLUMN,
            LayoutFamily.CARD_GRID,
            LayoutFamily.COMPARISON,
            LayoutFamily.METRICS_GRID,
            LayoutFamily.ROADMAP,
        ]
        chosen = alternator[index % len(alternator)]
        if recent and recent[-1] == chosen:
            chosen = LayoutFamily.TWO_COLUMN if chosen != LayoutFamily.TWO_COLUMN else LayoutFamily.CARD_GRID
        return chosen
