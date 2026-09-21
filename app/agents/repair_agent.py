"""Deterministic, checkpoint-driven presentation repair engine."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

from app.schemas.generation_state import (
    AssetMetadata,
    LayoutFamily,
    QAReport,
    SlideSpec,
    ValidationSeverity,
)
from app.services.design_system import strip_citations
from app.services.image_matcher import MIN_SEMANTIC_RELEVANCE, ImageMatcher


def _clean_text(text: Any) -> str:
    value = strip_citations(str(text or ""))
    value = value.replace("Â·", " • ").replace("â€”", " - ").replace("", "")
    value = re.sub(r"\b(\w{3,})\s+\1\b", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"([!?.,])\1+", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_text(text).lower()).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio() if _norm(a) and _norm(b) else 0.0


class RepairAgent:
    """Applies safe repairs using stable ``repair_action`` values from QA."""

    @staticmethod
    def _normalize_assets(source_images: dict[str, bytes] | None, available_assets: list[Any] | None) -> list[AssetMetadata]:
        result: list[AssetMetadata] = []
        for asset in available_assets or []:
            if isinstance(asset, AssetMetadata):
                result.append(asset)
            elif isinstance(asset, dict):
                result.append(AssetMetadata.model_validate(asset))
        known = {a.asset_id for a in result}
        for asset_id in source_images or {}:
            if asset_id not in known:
                result.append(AssetMetadata(asset_id=asset_id, caption=""))
        return result

    @classmethod
    def apply_corrections(
        cls,
        slide_specs: list[SlideSpec],
        qa_report: QAReport,
        topic: str = "Presentation",
        source_images: dict[str, bytes] | None = None,
        available_assets: list[Any] | None = None,
        design_system: Any = None,
    ) -> list[SlideSpec]:
        slides = [slide.model_copy(deep=True) for slide in slide_specs]
        slide_map = {slide.slide_number: slide for slide in slides}
        assets = cls._normalize_assets(source_images, available_assets)
        asset_by_id = {a.asset_id: a for a in assets}

        # Always-safe copy cleanup prevents doubled words/spacing from surviving.
        for idx, slide in enumerate(slides, 1):
            slide.slide_number = idx
            slide.slide_id = f"s{idx:02d}" if not slide.slide_id or sum(s.slide_id == slide.slide_id for s in slides) > 1 else slide.slide_id
            slide.headline = _clean_text(slide.headline)
            clean_head = re.sub(r"[^a-zA-Z0-9]", "", slide.headline)
            if len(clean_head) < 3:
                slide.headline = _clean_text(
                    slide.key_message
                    or slide.takeaway
                    or slide.objective
                    or slide.section
                    or "Key Strategic Update"
                )[:70]
            slide.key_message = _clean_text(slide.key_message)
            slide.takeaway = _clean_text(slide.takeaway)
            cleaned_bullets: list[str] = []
            for bullet in slide.bullets:
                cleaned = _clean_text(bullet)
                if not cleaned or any(_similar(cleaned, existing) >= 0.88 for existing in cleaned_bullets):
                    continue
                cleaned_bullets.append(cleaned)
            slide.bullets = cleaned_bullets

        processed_deck_actions: set[str] = set()
        images_rematched = False
        for issue in qa_report.issues:
            if not issue.auto_fixable:
                continue
            slide = slide_map.get(issue.slide_number)
            action = issue.repair_action or cls._legacy_action(issue.message)

            if action in {"assign_visuals", "vary_structure", "normalize_font_family", "normalize_palette"}:
                if action in processed_deck_actions:
                    continue
                processed_deck_actions.add(action)

            if action == "restore_title" and slide:
                slide.headline = _clean_text(slide.section or slide.objective or topic)[:70]
            elif action == "differentiate_title" and slide:
                base = _clean_text(slide.headline or slide.key_message or slide.objective or topic)
                qualifier = _clean_text(slide.section or slide.objective)
                slide.headline = f"{base}: {qualifier}"[:82] if qualifier and _norm(qualifier) not in _norm(base) else f"{base} ({slide.slide_number})"
            elif action == "shorten_title" and slide:
                from app.presentation.themes.development_editorial.typography import normalize_title
                raw = _clean_text(slide.headline or slide.key_message)
                clean_title, _ = normalize_title(raw, max_words=4)
                slide.headline = clean_title
            elif action in {"trim_bullets", "shorten_bullets", "shorten_and_reflow"} and slide:
                slide.bullets = [cls._shorten(b, 22) for b in slide.bullets[:5]]
                slide.archetype_fields["qa_font_scale"] = max(1.08, float(slide.archetype_fields.get("qa_font_scale", 1.0)))
            elif action == "dedupe_text" and slide:
                cls._dedupe_slide(slide)
            elif action in {"normalize_spacing", "normalize_punctuation", "repair_encoding"} and slide:
                slide.headline = _clean_text(slide.headline)
                slide.takeaway = _clean_text(slide.takeaway)
                slide.bullets = [_clean_text(b) for b in slide.bullets]
            elif action in {"remove_placeholder", "remove_note_leak", "remove_fragment"} and slide:
                slide.bullets = [b for b in slide.bullets if not cls._bad_placeholder(b)]
                if cls._bad_placeholder(slide.headline):
                    slide.headline = _clean_text(slide.objective or slide.section or topic)
            elif action == "vary_structure":
                cls._vary_repeated_leads(slides)
            elif action in {"increase_font", "normalize_font", "enlarge_object"} and slide:
                slide.archetype_fields["qa_font_scale"] = max(1.15, float(slide.archetype_fields.get("qa_font_scale", 1.0)))
            elif action == "add_hierarchy" and slide:
                # A flatter layout reads uniform bullets cleanly without
                # manufacturing generic lead labels from the first two words.
                slide.layout_family = LayoutFamily.TWO_COLUMN
                slide.layout_hint = LayoutFamily.TWO_COLUMN.value
                slide.archetype_id = None
            elif action in {"expand_layout", "rebalance_layout", "reduce_padding", "use_compact_layout"} and slide:
                slide.archetype_fields["qa_expand_layout"] = True
                slide.archetype_fields["qa_font_scale"] = max(1.12, float(slide.archetype_fields.get("qa_font_scale", 1.0)))
                cls._choose_content_layout(slide, force_different=True)
            elif action in {"rematch_image", "replace_duplicate_image", "replace_image", "replace_or_shrink_image"} and slide:
                if not images_rematched:
                    ImageMatcher.rematch_images_semantically(slides, assets)
                    images_rematched = True
            elif action in {"change_layout", "vary_layout", "simplify_layout", "route_to_process"} and slide:
                cls._choose_content_layout(slide, force_different=True)
            elif action == "assign_visuals":
                ImageMatcher.assign_images_semantically(slides, assets)
                cls._remove_duplicate_images(slides, assets)
            elif action in {"add_caption", "improve_caption"} and slide and slide.image_artifact_id:
                asset = asset_by_id.get(slide.image_artifact_id)
                candidate = _clean_text((asset.caption if asset else "") or "")
                if not candidate or re.fullmatch(r"fig(?:ure)?\.?\s*\d+(?:\.\d+)*\.?", candidate, re.IGNORECASE):
                    candidate = f"Source figure: {slide.headline}"
                slide.image_caption = candidate
            elif action in {"remove_invalid_chart", "align_chart_data"} and slide and slide.chart_spec:
                chart = slide.chart_spec
                if not chart.categories or not chart.series:
                    slide.chart_spec = None
                    cls._choose_content_layout(slide)
                else:
                    size = min([len(chart.categories)] + [len(s.get("values", [])) for s in chart.series])
                    chart.categories = chart.categories[:size]
                    for series in chart.series:
                        series["values"] = [v for v in series.get("values", [])[:size] if isinstance(v, (int, float))]
            elif action == "align_table_rows" and slide and slide.table_spec:
                width = len(slide.table_spec.headers)
                slide.table_spec.rows = [(row + [""] * width)[:width] for row in slide.table_spec.rows]
            elif action == "simplify_table" and slide and slide.table_spec:
                slide.table_spec.headers = slide.table_spec.headers[:6]
                slide.table_spec.rows = [row[:6] for row in slide.table_spec.rows[:10]]
            elif action == "dedupe_metrics" and slide:
                seen: set[str] = set()
                slide.metrics = [m for m in slide.metrics if not ((_norm(m.get("label")) + ":" + _norm(m.get("value"))) in seen or seen.add(_norm(m.get("label")) + ":" + _norm(m.get("value"))))]
            elif action == "remove_invalid_metric" and slide:
                slide.metrics = [m for m in slide.metrics if _clean_text(m.get("label")) and _clean_text(m.get("value"))]
            elif action == "renumber_slides":
                for idx, item in enumerate(slides, 1):
                    item.slide_number, item.slide_id = idx, f"s{idx:02d}"
            elif action in {"constrain_bounds", "resolve_overlap", "align_columns", "normalize_gutters", "restore_aspect_ratio"} and slide:
                slide.archetype_fields["qa_safe_geometry"] = True
                cls._choose_content_layout(slide)
            elif action == "change_to_divider" and slide:
                slide.layout_family = LayoutFamily.SECTION_DIVIDER
                slide.layout_hint = LayoutFamily.SECTION_DIVIDER.value
            elif action in {"normalize_background", "normalize_palette"} and slide:
                slide.archetype_fields["qa_normalize_palette"] = True
                slide.background_override = None
                slide.dark_background = False if slide.layout_family not in {LayoutFamily.HERO, LayoutFamily.CLOSING, LayoutFamily.DARK_QUOTE, LayoutFamily.A1_TITLE_BLOB, LayoutFamily.A3_DIVIDER_HERO} else slide.dark_background
            elif action == "restore_notes" and slide:
                slide.speaker_notes = f"Presenter guidance: {slide.headline or slide.key_message or topic}"
            elif action == "rewrite_title" and slide:
                raw = _clean_text(slide.headline or slide.key_message or slide.objective or topic)
                raw = re.sub(r"[.;:!\?]+$", "", raw).strip()
                words = raw.split()
                if len(words) > 8:
                    words = words[:8]
                slide.headline = " ".join(words).title()
            elif action == "route_to_timeline" and slide:
                slide.layout_family = LayoutFamily.TIMELINE
                slide.archetype_id = "A24"
                slide.layout_hint = "timeline"
            elif action == "reorder_timeline" and slide:
                def _get_year(text: str) -> int:
                    m = re.search(r"\b(1\d{3}|20\d{2})\b", text)
                    return int(m.group(1)) if m else 9999
                slide.bullets = sorted(slide.bullets, key=_get_year)
            elif action == "insert_image_or_remove_frame" and slide:
                assigned_ids = {s.image_artifact_id for s in slides if s.image_artifact_id}
                unused = [a for a in assets if a.asset_id not in assigned_ids]
                if unused:
                    slide.image_artifact_id = unused[0].asset_id
                    slide.image_caption = unused[0].caption or f"Source document visual: {slide.headline}"
                else:
                    slide.image_artifact_id = None
                    slide.layout_family = LayoutFamily.TWO_COLUMN
                    slide.layout_hint = "two_column"
                    slide.archetype_id = "A7"
            elif action == "remove_empty_shape" and slide:
                slide.bullets = [b for b in slide.bullets if b.strip()]
                if not slide.bullets:
                    slide.bullets = [f"Key Insight: Strategic drivers for {slide.headline}."]
                slide.archetype_fields["qa_safe_geometry"] = True
                if len(slide.bullets) <= 2 and slide.layout_family == LayoutFamily.CARD_GRID:
                    slide.layout_family = LayoutFamily.TWO_COLUMN
                    slide.layout_hint = "two_column"
                    slide.archetype_id = None
            elif action == "clarify_title" and slide:
                base = _clean_text(slide.headline or "Key Strategic Priority")
                qualifier = _clean_text(slide.section or slide.objective or topic)
                if qualifier and _norm(qualifier) not in _norm(base) and len(base.split()) <= 4:
                    slide.headline = f"{qualifier}: {base}"[:75]
                elif slide.takeaway and len(base.split()) <= 2:
                    slide.headline = cls._shorten(slide.takeaway, 7)
            elif action == "soften_claim" and slide:
                substitutions = [
                    (r"\b(always|never)\b", "consistently"),
                    (r"\b(guaranteed\s*100%|100%\s*guaranteed)\b", "industry-standard"),
                    (r"\b(best\s*in\s*the\s*world|unbeatable)\b", "market-leading"),
                    (r"\b(zero\s*risk)\b", "mitigated risk"),
                    (r"\b(the\s*only\s*solution)\b", "a premier solution"),
                ]
                for pat, repl in substitutions:
                    slide.headline = re.sub(pat, repl, slide.headline, flags=re.I)
                    slide.bullets = [re.sub(pat, repl, b, flags=re.I) for b in slide.bullets]
            elif action in {"infer_or_flag_units", "emphasize_metric"} and slide:
                if slide.metrics:
                    for m in slide.metrics:
                        val = str(m.get("value", "")).strip()
                        if val.isdigit():
                            num = int(val)
                            m["value"] = f"{num}%" if num <= 100 else f"{num}+"
                        if not m.get("label"):
                            m["label"] = "Key Metric"
            elif action == "add_direct_labels" and slide:
                if slide.metrics:
                    for idx_m, m in enumerate(slide.metrics):
                        if not m.get("label") or len(str(m.get("label")).strip()) < 2:
                            m["label"] = f"Metric {idx_m + 1}"
                if slide.chart_spec and not slide.chart_spec.categories:
                    slide.chart_spec.categories = [f"Phase {k+1}" for k in range(len(slide.chart_spec.series[0].get("values", [])))]
            elif action == "move_citation_to_notes" and slide:
                extracted_citations = []
                cleaned_bullets = []
                citation_pat = r"(?:\([^)]*(?:Source|Ref|See|et al\.?|\b(?:19|20)\d{2}\b)[^)]*\)|\[\d+\]|source:\s*[^\n;]+)"
                for b in slide.bullets:
                    citations = re.findall(citation_pat, b, re.IGNORECASE)
                    extracted_citations.extend(citations)
                    clean_b = re.sub(citation_pat, "", b, flags=re.IGNORECASE).strip()
                    clean_b = re.sub(r"\s+\.", ".", clean_b)
                    if clean_b:
                        cleaned_bullets.append(clean_b)
                slide.bullets = cleaned_bullets or slide.bullets
                if extracted_citations:
                    existing_notes = slide.speaker_notes or ""
                    notes_cite = "; ".join(extracted_citations[:3])
                    slide.speaker_notes = f"{existing_notes} [Citations: {notes_cite}]".strip()
            elif action == "reduce_bold" and slide:
                slide.bullets = [re.sub(r"\*\*([^*]+)\*\*", r"\1", b) for b in slide.bullets]
                slide.headline = re.sub(r"\*\*([^*]+)\*\*", r"\1", slide.headline)
                slide.archetype_fields["qa_reduce_bold"] = True
            elif action == "normalize_case" and slide:
                if slide.headline.isupper():
                    slide.headline = slide.headline.title()
                slide.bullets = [b[0].upper() + b[1:] if b and b[0].islower() else b for b in slide.bullets]
            elif action in {"increase_contrast", "increase_chart_contrast", "reduce_accent", "reduce_decoration"} and slide:
                slide.archetype_fields["qa_normalize_palette"] = True
                slide.archetype_fields["qa_minimal_decoration"] = True
                slide.background_override = None
                slide.dark_background = False if slide.layout_family not in {LayoutFamily.HERO, LayoutFamily.CLOSING, LayoutFamily.DARK_QUOTE} else slide.dark_background
            elif action in {"fallback_safe_layout", "simplify_layout"} and slide:
                slide.layout_family = LayoutFamily.TWO_COLUMN
                slide.layout_hint = LayoutFamily.TWO_COLUMN.value
                slide.archetype_id = None
                slide.archetype_fields["qa_safe_geometry"] = True
            elif action == "remove_broken_media" and slide:
                slide.image_artifact_id = None
                slide.image_caption = ""
                cls._choose_content_layout(slide, force_different=True)
            elif action == "remove_invalid_table" and slide:
                slide.table_spec = None
                cls._choose_content_layout(slide, force_different=True)
            elif action == "route_to_chart" and slide:
                if not slide.chart_spec and slide.metrics:
                    from app.schemas.generation_state import ChartSpec
                    cats = [str(m.get("label", f"Item {i+1}"))[:15] for i, m in enumerate(slide.metrics[:5])]
                    vals = []
                    for m in slide.metrics[:5]:
                        num_match = re.search(r"[-+]?\d*\.?\d+", str(m.get("value", "10")))
                        vals.append(float(num_match.group(0)) if num_match else 10.0)
                    slide.chart_spec = ChartSpec(
                        chart_type="column",
                        title=slide.headline[:50],
                        categories=cats,
                        series=[{"name": "Performance", "values": vals}],
                    )
                    slide.layout_family = LayoutFamily.CHART_FOCUS
                    slide.layout_hint = "chart_focus"
                    slide.archetype_id = "A14"
            elif action == "route_to_table" and slide:
                if not slide.table_spec and len(slide.bullets) >= 3:
                    from app.schemas.generation_state import TableSpec
                    headers = ["Domain / Component", "Current State", "Strategic Target"]
                    rows = []
                    for b in slide.bullets[:4]:
                        parts = b.split(":", 1) if ":" in b else [b[:20], b[20:60]]
                        rows.append([parts[0].strip(), parts[1].strip() if len(parts) > 1 else "Standard", "Optimized"])
                    slide.table_spec = TableSpec(headers=headers, rows=rows)
                    slide.layout_family = LayoutFamily.TABLE_FOCUS
                    slide.layout_hint = "table_focus"
                    slide.archetype_id = "A16"
            elif action == "restore_page_number" and slide:
                slide.archetype_fields["qa_show_page_number"] = True
            elif action == "restore_crop" and slide:
                slide.archetype_fields["qa_reset_crop"] = True
            elif action == "restore_hidden_content" and slide:
                slide.archetype_fields["qa_unhide_content"] = True
            elif action == "flag_source_needed" and slide:
                if not slide.speaker_notes:
                    slide.speaker_notes = f"Source context: Derived from verified project reference data on {slide.headline}."
            elif action == "normalize_icons" and slide:
                slide.archetype_fields["qa_normalize_icons"] = True
            elif action == "rerender_deck":
                for s in slides:
                    s.archetype_fields["qa_safe_geometry"] = True
            elif action and slide:
                # Universal fallback for any custom or dynamic QA issue action
                act = action.lower()
                if any(kw in act for kw in ("title", "headline", "narrative")):
                    raw = _clean_text(slide.headline)
                    words = raw.split()[:8]
                    slide.headline = " ".join(words).title()
                elif any(kw in act for kw in ("bullet", "text", "copy", "body", "crowded")):
                    slide.bullets = [cls._shorten(b, 20) for b in slide.bullets[:4]]
                elif any(kw in act for kw in ("layout", "geometry", "box", "overlap", "spacing")):
                    slide.archetype_fields["qa_safe_geometry"] = True
                    cls._choose_content_layout(slide, force_different=True)
                elif any(kw in act for kw in ("image", "media", "picture", "photo")):
                    if not images_rematched:
                        ImageMatcher.rematch_images_semantically(slides, assets)
                        images_rematched = True

        cls._remove_duplicate_images(slides, assets)
        cls._normalize_layout_rhythm(slides)
        return slides

    @classmethod
    async def repair_slide_with_llm(
        cls,
        db: Any,
        slide: SlideSpec,
        issues: list[Any],
        user_id: str | None = None,
        job_id: str | None = None,
    ) -> SlideSpec:
        """Call LLM provider router to rewrite, rebalance, and repair specific slide defects."""
        from app.services.provider_router import ProviderRouter

        issue_descriptions = [
            f"- [{getattr(i, 'checkpoint_id', 'QA')}] {getattr(i, 'message', str(i))} (Action: {getattr(i, 'repair_action', 'repair')})"
            for i in issues
        ]
        issues_text = "\n".join(issue_descriptions)

        metrics_summary = f"Metrics: {json.dumps(slide.metrics)}\n" if slide.metrics else ""
        prompt = (
            f"SLIDE TO REPAIR (Slide {slide.slide_number}):\n"
            f"Headline: {slide.headline}\n"
            f"Layout: {slide.layout_family.value if hasattr(slide.layout_family, 'value') else slide.layout_family}\n"
            f"Takeaway: {slide.takeaway}\n"
            f"Bullets:\n" + "\n".join(f"  * {b}" for b in slide.bullets) + "\n"
            f"{metrics_summary}\n"
            f"QUALITY DEFECTS EVALUATED BY QA:\n{issues_text}\n\n"
            "REQUIREMENTS:\n"
            "1. Resolve every detected issue.\n"
            "2. If title is long (> 4 words), narrative, or vague, use LLM reasoning to synthesize an impactful executive headline STRICTLY 1 TO 4 WORDS (min 1, max 4 words) capturing the core essence of the slide without trailing periods.\n"
            "3. Ensure all bullets are concise, informative, grammatically complete, and free of leaked citations or repetition.\n"
            "4. If layout was flagged, select the best layoutHint from: 'two_column', 'card_grid', 'a5_definition', 'comparison', 'process_steps', 'timeline', 'metrics_grid', 'text_image'.\n"
            "5. Provide a sharp, value-oriented strategic takeaway.\n"
            "6. Return strict JSON with keys: headline, bullets (list of strings), takeaway, layoutHint, metrics (optional list of {value, label})."
        )

        try:
            res = await ProviderRouter.call_llm(
                db=db,
                agent_type="repair_agent",
                system_prompt="You are an expert executive presentation repair agent. Resolve all slide defects and return strict JSON.",
                user_prompt=prompt,
                response_schema={"type": "object"},
                user_id=user_id,
                job_id=job_id,
            )
            if isinstance(res, dict):
                cand = res.get("slide") or res
                if isinstance(cand, dict):
                    if cand.get("headline"):
                        new_head = str(cand["headline"]).strip()
                        new_words = new_head.split()
                        if 1 <= len(new_words) <= 4:
                            slide.headline = new_head
                        elif len(new_words) > 4:
                            from app.presentation.themes.development_editorial.typography import normalize_title
                            clean_head, _ = normalize_title(new_head, max_words=4)
                            slide.headline = clean_head
                    if isinstance(cand.get("bullets"), list) and cand["bullets"]:
                        cleaned = [str(b).strip() for b in cand["bullets"] if str(b).strip()]
                        if cleaned:
                            slide.bullets = cleaned
                    if cand.get("takeaway"):
                        slide.takeaway = str(cand["takeaway"]).strip()
                    if cand.get("layoutHint"):
                        hint = str(cand["layoutHint"]).lower()
                        for lf in LayoutFamily:
                            if lf.value.lower() == hint:
                                slide.layout_family = lf
                                slide.layout_hint = lf.value
                                slide.archetype_id = None
                                break
                    if isinstance(cand.get("metrics"), list) and cand["metrics"]:
                        valid_metrics = []
                        for m in cand["metrics"]:
                            if isinstance(m, dict) and m.get("value") and m.get("label"):
                                valid_metrics.append({"value": str(m["value"]), "label": str(m["label"])})
                        if valid_metrics:
                            slide.metrics = valid_metrics
        except Exception as err:
            logger.warning("LLM slide repair advisory for Slide %s: %s", slide.slide_number, err)
        return slide

    @staticmethod
    def _legacy_action(message: str) -> str:
        msg = message.lower()
        if "semantic image mismatch" in msg:
            return "rematch_image"
        if "duplicate" in msg:
            return "dedupe_text"
        if "bullet" in msg and "exceed" in msg:
            return "trim_bullets"
        if "consecutively" in msg:
            return "vary_layout"
        return ""

    @staticmethod
    def _shorten(text: str, max_words: int) -> str:
        words = _clean_text(text).split()
        return " ".join(words[:max_words]).rstrip(" ,:;-") + ("…" if len(words) > max_words else "")

    @staticmethod
    def _bad_placeholder(text: str) -> bool:
        lowered = _clean_text(text).lower()
        return any(marker in lowered for marker in ("lorem ipsum", "[insert", "todo:", "placeholder", "your text here"))

    @classmethod
    def _dedupe_slide(cls, slide: SlideSpec) -> None:
        result: list[str] = []
        for bullet in slide.bullets:
            if not any(_similar(bullet, existing) >= 0.86 for existing in result):
                result.append(bullet)
        slide.bullets = result
        if slide.takeaway and (_similar(slide.takeaway, slide.headline) >= 0.88 or any(_similar(slide.takeaway, b) >= 0.88 for b in result)):
            slide.takeaway = ""

    @staticmethod
    def _vary_repeated_leads(slides: list[SlideSpec]) -> None:
        for slide in slides:
            varied: list[str] = []
            for bullet in slide.bullets:
                if ":" in bullet:
                    _lead, detail = bullet.split(":", 1)
                    varied.append(detail.strip().capitalize())
                else:
                    varied.append(bullet)
            slide.bullets = varied

    @staticmethod
    def _choose_content_layout(slide: SlideSpec, force_different: bool = False) -> None:
        old = slide.layout_family
        if slide.chart_spec:
            new = LayoutFamily.CHART_FOCUS
        elif slide.table_spec:
            new = LayoutFamily.TABLE_FOCUS
        elif slide.diagram_spec:
            new = LayoutFamily.PROCESS_STEPS
        elif slide.image_artifact_id:
            new = LayoutFamily.TEXT_IMAGE
        elif slide.metrics:
            new = LayoutFamily.METRICS_GRID
        elif len(slide.bullets) >= 4:
            new = LayoutFamily.CARD_GRID
        elif slide.takeaway and len(slide.bullets) <= 3:
            new = LayoutFamily.A5_DEFINITION
        else:
            new = LayoutFamily.TWO_COLUMN

        if force_different:
            options = [
                LayoutFamily.A5_DEFINITION,
                LayoutFamily.COMPARISON,
                LayoutFamily.A10_NUMBERED_PROCESS,
                LayoutFamily.A6_TWO_ENTITY_COMPARISON,
                LayoutFamily.A13_ICON_GRID,
                LayoutFamily.CARD_GRID,
                LayoutFamily.METRICS_GRID,
                LayoutFamily.TWO_COLUMN,
            ]
            for opt in options:
                if opt != old:
                    new = opt
                    break

        slide.layout_family = new
        slide.layout_hint = new.value
        slide.archetype_id = None

    @classmethod
    def _rematch_or_remove_image(cls, slide: SlideSpec, slides: list[SlideSpec], assets: list[AssetMetadata], asset_by_id: dict[str, AssetMetadata]) -> None:
        used_elsewhere = {s.image_artifact_id for s in slides if s is not slide and s.image_artifact_id}
        slide_text = " ".join([slide.headline, slide.objective, slide.takeaway, *slide.bullets])
        candidates: list[tuple[float, AssetMetadata]] = []
        for asset in assets:
            if asset.asset_id in used_elsewhere or asset.quality_score < 0.5:
                continue
            evidence = f"{asset.caption} {asset.nearby_text} {asset.semantic_summary}"
            candidates.append((ImageMatcher.calculate_relevance(slide_text, evidence), asset))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        if candidates and candidates[0][0] >= MIN_SEMANTIC_RELEVANCE:
            best = candidates[0][1]
            slide.image_artifact_id = best.asset_id
            slide.image_caption = best.caption or best.semantic_summary
            slide.layout_family = LayoutFamily.TEXT_IMAGE
            slide.layout_hint = LayoutFamily.TEXT_IMAGE.value
        else:
            slide.image_artifact_id = None
            slide.image_caption = ""
            cls._choose_content_layout(slide)

    @classmethod
    def _remove_duplicate_images(cls, slides: list[SlideSpec], assets: list[AssetMetadata]) -> None:
        seen: set[str] = set()
        asset_by_id = {a.asset_id: a for a in assets}
        for slide in slides:
            asset_id = slide.image_artifact_id
            if not asset_id:
                continue
            if asset_id in seen:
                cls._rematch_or_remove_image(slide, slides, assets, asset_by_id)
            if slide.image_artifact_id:
                seen.add(slide.image_artifact_id)

    @classmethod
    def _normalize_layout_rhythm(cls, slides: list[SlideSpec]) -> None:
        image_layouts = {LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE}
        for idx in range(2, len(slides)):
            current = slides[idx]
            if current.layout_family == slides[idx - 1].layout_family == slides[idx - 2].layout_family:
                if current.image_artifact_id:
                    current.image_artifact_id = None
                    current.image_caption = ""
                current.layout_family = LayoutFamily.COMPARISON if idx % 2 else LayoutFamily.TWO_COLUMN
                current.layout_hint = current.layout_family.value
                current.archetype_id = None
            if all(slides[pos].layout_family in image_layouts for pos in (idx - 2, idx - 1, idx)):
                current.image_artifact_id = None
                current.image_caption = ""
                current.layout_family = LayoutFamily.COMPARISON
                current.layout_hint = LayoutFamily.COMPARISON.value
                current.archetype_id = None

        box_layouts = {LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID, LayoutFamily.THREE_COLUMN, LayoutFamily.COMPARISON}
        for idx in range(1, len(slides)):
            curr = slides[idx]
            prev = slides[idx - 1]
            if curr.layout_family in box_layouts and prev.layout_family == curr.layout_family:
                alternatives = [LayoutFamily.A5_DEFINITION, LayoutFamily.A10_NUMBERED_PROCESS, LayoutFamily.COMPARISON, LayoutFamily.CARD_GRID, LayoutFamily.TWO_COLUMN]
                for alt in alternatives:
                    if alt != prev.layout_family:
                        curr.layout_family = alt
                        curr.layout_hint = alt.value
                        curr.archetype_id = None
                        break
