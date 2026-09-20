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
from app.services.design_system import clean_text

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
        explicit_slides = getattr(goal, "explicit_slides", []) or []

        # Semantically match available assets to slides first, preventing wrong image assignment
        if assets and slides_input:
            from app.services.image_matcher import ImageMatcher
            ImageMatcher.assign_images_semantically(slides_input, assets)

        # Layout rhythm tracker
        recent_layouts: list[LayoutFamily] = []
        recent_archetypes: list[str] = []

        for i in range(count):
            slide_id = f"s{i+1:02d}"
            raw_slide = slides_input[i] if i < len(slides_input) and isinstance(slides_input[i], dict) else {}
            explicit_s = explicit_slides[i] if i < len(explicit_slides) and isinstance(explicit_slides[i], dict) else {}

            # 1. Slide Role & Position
            is_first = (i == 0)
            is_last = (i == count - 1)

            purpose = raw_slide.get("purpose") or explicit_s.get("purpose") or raw_slide.get("objective") or f"Key topic analysis for section {i+1}"
            headline = raw_slide.get("headline") or explicit_s.get("headline") or raw_slide.get("message") or f"Strategic Milestone {i+1}: Delivering Scalable Value"
            raw_b = raw_slide.get("bullets") or explicit_s.get("bullets") or []
            bullets = []
            for b in raw_b:
                if isinstance(b, dict):
                    lbl = b.get("label") or b.get("title") or b.get("header") or ""
                    val = b.get("value") or b.get("description") or b.get("text") or ""
                    if lbl and val:
                        txt = f"{lbl}: {val}"
                    else:
                        txt = str(lbl or val)
                    if txt.strip():
                        bullets.append(clean_text(txt).strip())
                elif isinstance(b, str) and clean_text(b).strip():
                    txt = re.sub(r"^(?:evidence|interpretation|observation|fact|takeaway|role)\s*:\s*", "", clean_text(b), flags=re.IGNORECASE).strip()
                    if txt:
                        bullets.append(txt)


            # 2. Select Layout Family with Visual Rhythm
            layout_hint = raw_slide.get("layoutHint") or raw_slide.get("layout_hint") or explicit_s.get("layoutHint") or ""
            chosen_layout = cls._determine_layout(
                i, count, layout_hint, recent_layouts, raw_slide, assets, goal
            )

            # 3. Associate Visual Assets (Images / Figures)
            img_id = raw_slide.get("imageArtifactId") or raw_slide.get("image_artifact_id")
            caption = raw_slide.get("imageCaption") or raw_slide.get("image_caption") or ""

            if img_id and not caption and assets:
                match = next((a for a in assets if a.asset_id == img_id), None)
                if match and match.caption:
                    caption = match.caption

            # If layout is IMAGE_FOCUS but no image was semantically matched, fall back to analytical layout
            if chosen_layout in (LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE) and not img_id and not is_first:
                alternatives = [LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID, LayoutFamily.COMPARISON, LayoutFamily.METRICS_GRID]
                chosen_layout = alternatives[i % len(alternatives)]

            is_consecutive_repeat = bool(recent_layouts) and recent_layouts[-1] == chosen_layout
            recent_layouts.append(chosen_layout)


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
                topic_context = f"{goal.topic} {purpose} {headline}".lower()
                is_financial_topic = any(w in topic_context for w in ("revenue", "arr", "mrr", "financial", "growth trajectory", "ebitda", "fiscal", "sales", "valuation"))
                if is_financial_topic:
                    chart_spec = ChartSpec(
                        chart_type=ChartType.COLUMN,
                        title="Performance & Scaling Growth Trajectory",
                        categories=["FY22", "FY23", "FY24", "FY25 (Proj)"],
                        series=[{"name": "Enterprise ARR ($M)", "values": [12.4, 24.8, 48.2, 85.0]}],
                        units="$M",
                        source_provenance="Internal Operational Data",
                    )
                else:
                    chosen_layout = LayoutFamily.COMPARISON if len(bullets) == 2 else LayoutFamily.CARD_GRID

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
                arrow_steps = [
                    part.strip()
                    for part in re.split(r"\s*(?:→|->|⟶)​?\s*", headline)
                    if part.strip()
                ]
                if len(arrow_steps) >= 2:
                    nodes = [
                        DiagramNode(
                            label=f"{node_index + 1}. {label}",
                            subtext=bullets[node_index] if node_index < len(bullets) else purpose,
                        )
                        for node_index, label in enumerate(arrow_steps[:5])
                    ]
                else:
                    source_items = bullets[:5] or [purpose or headline]
                    nodes = []
                    for node_index, item in enumerate(source_items):
                        if ":" in item:
                            label, subtext = item.split(":", 1)
                        else:
                            words = item.split()
                            label = " ".join(words[:5])
                            subtext = " ".join(words[5:]) or item
                        nodes.append(
                            DiagramNode(
                                label=f"{node_index + 1}. {label.strip()}",
                                subtext=subtext.strip(),
                            )
                        )
                diagram_spec = DiagramSpec(
                    diagram_type="process",
                    nodes=nodes,
                )
            elif chosen_layout == LayoutFamily.MATRIX_QUADRANT:
                matrix_items = bullets[:4] or [purpose or headline]
                diagram_spec = DiagramSpec(
                    diagram_type="matrix",
                    nodes=[
                        DiagramNode(
                            label=(item.split(":", 1)[0] if ":" in item else " ".join(item.split()[:5])),
                            subtext=(item.split(":", 1)[1].strip() if ":" in item else item),
                        )
                        for item in matrix_items
                    ]
                )

            # 7. Construct SlideSpec
            if raw_slide.get("eyebrow"):
                eyebrow = raw_slide.get("eyebrow")
            elif raw_slide.get("chapter"):
                eyebrow = raw_slide.get("chapter")
            elif getattr(goal, "presentation_type", None) == PresentationType.RESEARCH_EDUCATION:
                eyebrow = f"Chapter {(i // 4) + 1}"
            else:
                eyebrow = f"Section {(i // 4) + 1}"

            takeaway = raw_slide.get("takeaway") or explicit_s.get("takeaway") or ""
            speaker_notes = raw_slide.get("speakerNotes") or raw_slide.get("speaker_notes") or f"Presenter guidance: {headline}"

            # Select consulting layout archetype
            from app.services.deck_archetypes import ArchetypeSelector, LAYOUT_ARCHETYPES
            arch_id = raw_slide.get("archetype_id") or raw_slide.get("archetype")
            raw_hint = (raw_slide.get("layoutHint") or raw_slide.get("layout_hint") or "").lower()

            if arch_id and arch_id.upper() in LAYOUT_ARCHETYPES:
                arch_id = arch_id.upper()
            elif raw_hint.upper() in LAYOUT_ARCHETYPES:
                arch_id = raw_hint.upper()
            elif raw_hint in ("big_questions", "timeline_band", "council_eight", "two_highways", "forts_quote_emblem", "concept_definition_image", "stepped_value_chain"):
                layout_to_arch = {
                    "big_questions": "A29", "timeline_band": "A24", "council_eight": "A25",
                    "two_highways": "A26", "forts_quote_emblem": "A27",
                    "concept_definition_image": "A28", "stepped_value_chain": "A30",
                }
                arch_id = layout_to_arch[raw_hint]
            elif raw_hint in ("hero", "roadmap", "bar_chart", "timeline", "quote") and not raw_slide.get("archetype_id") and not raw_slide.get("archetype"):
                arch_id = None
            elif raw_hint in ("comparison", "two_column") and not raw_slide.get("archetype_id") and not raw_slide.get("archetype"):
                if is_consecutive_repeat:
                    arch_id = "A26"
                elif raw_hint == "two_column" and not img_id and bullets and len(bullets) <= 3 and all(len(str(b).split()) <= 10 for b in bullets):
                    arch_id = "A6"
                else:
                    arch_id = None
            elif is_last and count > 1 and (not raw_hint or raw_hint in ("closing", "takeaways")):
                arch_id = "A17"


            else:
                # Vary with consulting archetype for unconstrained, editorial, hierarchy, or repeating layouts
                if is_first and count > 1 and (not raw_hint or raw_hint in ("hero", "title")):
                    c_type = "title"
                elif is_last and count > 1 and (not raw_hint or raw_hint in ("closing", "takeaways")):
                    c_type = "closing"
                elif chart_spec:
                    c_type = "chart"
                elif table_spec:
                    c_type = "table"
                elif raw_hint in ArchetypeSelector.CONTENT_TYPE_MAP:
                    c_type = raw_hint
                elif raw_slide.get("metrics") or chosen_layout == LayoutFamily.METRICS_GRID:
                    c_type = "stat_highlight"
                elif chosen_layout in (LayoutFamily.COMPARISON, LayoutFamily.TWO_COLUMN) or "comparison" in raw_hint:
                    c_type = "two_highways" if recent_layouts and recent_layouts[-1] == chosen_layout else "comparison"
                elif chosen_layout == LayoutFamily.PROCESS_STEPS or "process" in raw_hint:
                    c_type = "process"
                elif "definition" in raw_hint or "definition" in purpose.lower():
                    c_type = "definition"
                elif "quote" in raw_hint or "quote" in purpose.lower():
                    c_type = "quote"
                elif "timeline" in raw_hint or "history" in purpose.lower():
                    c_type = "timeline"
                elif "hierarchy" in raw_hint or "council" in raw_hint or "command" in purpose.lower():
                    c_type = "council_eight"
                elif "questions" in raw_hint or "question" in purpose.lower():
                    c_type = "big_questions"
                elif "chain" in raw_hint or "value" in purpose.lower():
                    c_type = "value_chain"
                else:
                    c_type = "grid"

                prev_arch = recent_archetypes[-1] if recent_archetypes else None
                arch_id = ArchetypeSelector.select_archetype(
                    content_type=c_type,
                    content_summary=purpose,
                    previous_archetype=prev_arch,
                    has_image=bool(img_id),
                    has_chart=bool(chart_spec),
                    has_table=bool(table_spec),
                )

            if arch_id:
                recent_archetypes.append(arch_id)
                for lf in LayoutFamily:
                    if lf.value == arch_id or lf.name.startswith(f"{arch_id}_"):
                        chosen_layout = lf
                        break

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
                archetype_id=arch_id,
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

        purpose_lower = f"{raw_slide.get('purpose', '')} {raw_slide.get('headline', '')} {raw_slide.get('message', '')}".lower()
        bullets = raw_slide.get("bullets") or raw_slide.get("key_points") or []
        bullets_text = " ".join(str(b) for b in bullets)
        full_slide_text = f"{purpose_lower} {bullets_text}".lower()

        # Content-based layout selection
        if raw_slide.get("chart") or (goal.required_charts and index in (2, 5)):
            return LayoutFamily.CHART_FOCUS
        if raw_slide.get("table"):
            return LayoutFamily.TABLE_FOCUS
        if raw_slide.get("imageArtifactId") or raw_slide.get("image_artifact_id"):
            return LayoutFamily.IMAGE_FOCUS

        # History / Chronological Timeline Detection
        year_matches = re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2}|[1-9][0-9]{0,2}\s*(?:bce|ce|bc|ad))\b", full_slide_text)
        has_timeline_kw = bool(re.search(r"\b(timeline|chronolog\w*|milestones?|evolution|historical\s+progression|centur\w*|eras?|reign|dynast\w*|sequences?)\b", full_slide_text))
        if len(year_matches) >= 2 or (has_timeline_kw and len(year_matches) >= 1) or "timeline" in purpose_lower or "chronology" in purpose_lower:
            return LayoutFamily.TIMELINE

        if "divider" in purpose_lower or "part " in purpose_lower or "chapter " in purpose_lower:
            return LayoutFamily.SECTION_DIVIDER
        if "quote" in purpose_lower or "perspective" in purpose_lower or "voice of" in purpose_lower:
            return LayoutFamily.QUOTE
        if "vs" in purpose_lower or "versus" in purpose_lower or "comparison" in purpose_lower or "trade-off" in purpose_lower:
            return LayoutFamily.COMPARISON
        if "process" in purpose_lower or "step" in purpose_lower or "workflow" in purpose_lower:
            return LayoutFamily.PROCESS_STEPS
        if "roadmap" in purpose_lower:
            return LayoutFamily.TIMELINE
        if "matrix" in purpose_lower or "quadrant" in purpose_lower:
            return LayoutFamily.MATRIX_QUADRANT
        if "summary" in purpose_lower or "recap" in purpose_lower or "takeaway" in purpose_lower:
            return LayoutFamily.A17_CLOSING_TAKEAWAYS
        if raw_slide.get("metrics") and len(raw_slide["metrics"]) >= 2:
            return LayoutFamily.METRICS_GRID

        # Multi-archetype visual rhythm alternator to prevent repetitive box patterns
        alternator = [
            LayoutFamily.TWO_COLUMN,
            LayoutFamily.A5_DEFINITION,
            LayoutFamily.COMPARISON,
            LayoutFamily.CARD_GRID,
            LayoutFamily.A10_NUMBERED_PROCESS,
            LayoutFamily.METRICS_GRID,
            LayoutFamily.A13_ICON_GRID,
            LayoutFamily.A6_TWO_ENTITY_COMPARISON,
            LayoutFamily.ROADMAP,
        ]
        chosen = alternator[index % len(alternator)]
        if recent and recent[-1] == chosen:
            # Pick next non-matching archetype from alternator
            chosen = alternator[(index + 1) % len(alternator)]
        return chosen
