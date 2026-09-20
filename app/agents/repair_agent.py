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
            if not issue.auto_fixable or issue.severity == ValidationSeverity.LOW:
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
                raw = _clean_text(slide.headline or slide.key_message)
                words = raw.split()[:10]
                while len(" ".join(words)) > 82 and len(words) > 3:
                    words.pop()
                slide.headline = " ".join(words).rstrip(" ,:;-")
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
        """Call LLM provider router to rewrite and repair specific slide defects."""
        from app.services.provider_router import ProviderRouter
        
        issue_descriptions = [f"- [{getattr(i, 'checkpoint_id', 'QA')}] {getattr(i, 'message', str(i))} (Action: {getattr(i, 'repair_action', 'repair')})" for i in issues]
        issues_text = "\n".join(issue_descriptions)
        
        prompt = (
            f"SLIDE TO REPAIR (Slide {slide.slide_number}):\n"
            f"Headline: {slide.headline}\n"
            f"Layout: {slide.layout_family.value if hasattr(slide.layout_family, 'value') else slide.layout_family}\n"
            f"Takeaway: {slide.takeaway}\n"
            f"Bullets:\n" + "\n".join(f"  * {b}" for b in slide.bullets) + "\n\n"
            f"QUALITY DEFECTS DETECTED:\n{issues_text}\n\n"
            "REQUIREMENTS:\n"
            "1. Fix every detected issue.\n"
            "2. Ensure headline is concise (< 8 words), punchy, and executive-ready without trailing periods.\n"
            "3. Ensure all bullets are complete, grammatically correct sentences or structured key insights.\n"
            "4. Never output empty boxes, placeholders, or broken fragments.\n"
            "5. Return JSON object with keys: headline, bullets (list of strings), takeaway, layoutHint."
        )
        
        try:
            res = await ProviderRouter.call_llm(
                db=db,
                agent_type="repair_agent",
                system_prompt="You are an expert presentation repair agent. Fix quality defects in PowerPoint slides and return strict JSON.",
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
                        if len(new_words) <= 10:
                            slide.headline = new_head
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
                                break
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
