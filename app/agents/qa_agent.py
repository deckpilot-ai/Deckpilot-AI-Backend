"""Deterministic 120-checkpoint presentation QA engine."""

from __future__ import annotations

import hashlib
import io
import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from app.agents.qa_checkpoints import (
    CHECKPOINT_BY_ID,
    CHECKPOINT_ID_BY_SLUG,
    CHECKPOINTS,
    checkpoint_ids,
)
from app.agents.title_intelligence import TitleIntelligence
from app.schemas.generation_state import (
    AssetMetadata,
    DesignSystem,
    LayoutFamily,
    QAReport,
    SlideSpec,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.services.image_matcher import MIN_SEMANTIC_RELEVANCE, ImageMatcher
from app.tools.pptx_validator import PPTXValidator

logger = logging.getLogger(__name__)

_PLACEHOLDERS = ("lorem ipsum", "[insert", "todo:", "placeholder", "tbd", "your text here")
_SAFE_FONTS = {"arial", "calibri", "cambria", "segoe ui", "times new roman", "georgia", "trebuchet ms", "verdana"}
_IMAGE_LAYOUTS = {LayoutFamily.IMAGE_FOCUS, LayoutFamily.TEXT_IMAGE, LayoutFamily.A2_TITLE_SPLIT, LayoutFamily.A8_STAT_IMAGE_HIGHLIGHT}
_INTENTIONAL_SPARSE = {LayoutFamily.HERO, LayoutFamily.CLOSING, LayoutFamily.SECTION_DIVIDER, LayoutFamily.A1_TITLE_BLOB, LayoutFamily.A2_TITLE_SPLIT, LayoutFamily.A3_DIVIDER_HERO, LayoutFamily.A17_CLOSING_TAKEAWAYS}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).strip()


def _similar(a: str, b: str) -> float:
    a_norm, b_norm = _normalized(a), _normalized(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


class PresentationQAAgent:
    """Evaluates slide plans, assets, and rendered PPTX using stable checkpoint IDs."""

    @staticmethod
    def _issue(
        slug: str,
        severity: ValidationSeverity,
        category: ValidationCategory,
        slide_number: int,
        message: str,
        slide_id: str = "",
        suggested_fix: str | None = None,
        auto_fixable: bool = True,
    ) -> ValidationIssue:
        checkpoint_id = CHECKPOINT_ID_BY_SLUG[slug]
        checkpoint = CHECKPOINT_BY_ID[checkpoint_id]
        return ValidationIssue(
            checkpoint_id=checkpoint_id,
            severity=severity,
            category=category,
            slide_number=slide_number,
            slide_id=slide_id,
            message=message,
            suggested_fix=suggested_fix or checkpoint.description,
            auto_fixable=auto_fixable,
            repair_action=checkpoint.repair_action,
        )

    @staticmethod
    def _assets(source_images: dict[str, bytes] | None, available_assets: list[Any] | None) -> list[AssetMetadata]:
        result: list[AssetMetadata] = []
        for asset in available_assets or []:
            if isinstance(asset, AssetMetadata):
                result.append(asset)
            elif isinstance(asset, dict):
                result.append(AssetMetadata.model_validate(asset))
        known = {a.asset_id for a in result}
        for asset_id, image_bytes in (source_images or {}).items():
            if asset_id not in known:
                result.append(AssetMetadata(asset_id=asset_id, caption="", width=0, height=0, sha256=hashlib.sha256(image_bytes).hexdigest()))
        return result

    @classmethod
    def evaluate_presentation(
        cls,
        slide_specs: list[SlideSpec],
        design_system: DesignSystem,
        pptx_bytes: bytes | None = None,
        source_images: dict[str, bytes] | None = None,
        available_assets: list[Any] | None = None,
    ) -> QAReport:
        issues: list[ValidationIssue] = []
        assets = cls._assets(source_images, available_assets)
        asset_by_id = {asset.asset_id: asset for asset in assets}
        cls._check_content(slide_specs, issues)
        cls._check_data(slide_specs, issues)
        cls._check_images_and_rhythm(slide_specs, assets, asset_by_id, source_images or {}, issues)
        if pptx_bytes:
            cls._check_rendered_pptx(slide_specs, pptx_bytes, issues)

        # Preserve useful title-intelligence findings while giving them stable IDs.
        for old in TitleIntelligence.validate_titles([s.headline or s.key_message for s in slide_specs]):
            if "duplicate" not in old.message.lower():
                old.checkpoint_id = old.checkpoint_id or CHECKPOINT_ID_BY_SLUG["title_too_short"]
                old.repair_action = old.repair_action or "clarify_title"
                issues.append(old)

        # De-duplicate identical detector emissions.
        unique: dict[tuple[str, int, str], ValidationIssue] = {}
        for issue in issues:
            unique[(issue.checkpoint_id, issue.slide_number, issue.message)] = issue
        issues = list(unique.values())

        failed_ids = {issue.checkpoint_id for issue in issues if issue.checkpoint_id}
        has_critical = any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == ValidationSeverity.HIGH for i in issues)
        has_medium = any(i.severity == ValidationSeverity.MEDIUM for i in issues)
        status = "failed" if has_critical else ("issues_detected" if has_high or has_medium else "passed")
        weights = {ValidationSeverity.CRITICAL: 12.0, ValidationSeverity.HIGH: 5.0, ValidationSeverity.MEDIUM: 2.0, ValidationSeverity.LOW: 0.5}
        score = max(0.0, round(100.0 - sum(weights[i.severity] for i in issues), 1))
        repair_triggered = any(i.auto_fixable and i.severity in (ValidationSeverity.CRITICAL, ValidationSeverity.HIGH, ValidationSeverity.MEDIUM) for i in issues)

        return QAReport(
            status=status,
            overall_quality_score=score,
            issues=issues,
            checks_performed=checkpoint_ids(),
            slide_count=len(slide_specs),
            repair_triggered=repair_triggered,
            checkpoints_total=len(CHECKPOINTS),
            checkpoints_passed=len(CHECKPOINTS) - len(failed_ids),
            checkpoints_failed=len(failed_ids),
        )

    @classmethod
    def _check_content(cls, slides: list[SlideSpec], issues: list[ValidationIssue]) -> None:
        seen_titles: dict[str, int] = {}
        seen_bodies: list[tuple[int, str]] = []
        seen_ids: dict[str, int] = {}
        lead_slides: dict[str, set[int]] = defaultdict(set)

        for idx, slide in enumerate(slides, 1):
            sid = slide.slide_id
            title = _clean(slide.headline or slide.key_message or slide.objective)
            body_parts = [_clean(b) for b in slide.bullets if _clean(b)]
            body = " ".join(body_parts + [_clean(slide.takeaway)])
            layout = slide.layout_family

            if sid in seen_ids:
                issues.append(cls._issue("duplicate_slide_id", ValidationSeverity.HIGH, ValidationCategory.TECHNICAL, idx, f"Slide ID '{sid}' duplicates Slide {seen_ids[sid]}", sid))
            else:
                seen_ids[sid] = idx
            if slide.slide_number != idx:
                issues.append(cls._issue("slide_number_gap", ValidationSeverity.MEDIUM, ValidationCategory.TECHNICAL, idx, f"Planned slide number {slide.slide_number} should be {idx}", sid))
            if not title:
                issues.append(cls._issue("missing_title", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, "Slide has no title", sid))
            elif _normalized(title) in seen_titles:
                issues.append(cls._issue("duplicate_title", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Title duplicates Slide {seen_titles[_normalized(title)]}", sid))
            else:
                seen_titles[_normalized(title)] = idx
            if len(title) > 90 or len(title.split()) > 13:
                issues.append(cls._issue("title_too_long", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Title contains {len(title.split())} words", sid))
            if title and len(title.split()) == 1 and len(title) < 6 and idx > 1:
                issues.append(cls._issue("title_too_short", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, f"Title '{title}' is too vague", sid))
            if any(marker in title.lower() for marker in _PLACEHOLDERS):
                issues.append(cls._issue("title_placeholder", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, "Title contains placeholder copy", sid))

            has_structured_content = bool(
                body_parts or _clean(slide.takeaway) or slide.metrics or slide.chart_spec
                or slide.table_spec or slide.diagram_spec or slide.quote or slide.image_artifact_id
            )
            if idx > 1 and layout not in _INTENTIONAL_SPARSE and not has_structured_content:
                issues.append(cls._issue("empty_body", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, "Content slide has no body, visual, chart, table, or diagram", sid))
            if len(body_parts) > 6:
                issues.append(cls._issue("too_many_bullets", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Slide has {len(body_parts)} bullets", sid))

            normalized_bullets: list[str] = []
            for bullet in body_parts:
                if len(bullet.split()) > 28:
                    issues.append(cls._issue("bullet_too_long", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Bullet exceeds 28 words: '{bullet[:60]}…'", sid))
                norm = _normalized(bullet)
                if norm in normalized_bullets:
                    issues.append(cls._issue("duplicate_bullet", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Duplicate bullet: '{bullet[:70]}'", sid))
                elif any(_similar(bullet, previous) >= 0.88 for previous in body_parts[:len(normalized_bullets)]):
                    issues.append(cls._issue("near_duplicate_bullet", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Near-duplicate bullet: '{bullet[:70]}'", sid))
                normalized_bullets.append(norm)
                if re.search(r"\b(\w{3,})\s+\1\b", bullet, re.IGNORECASE):
                    issues.append(cls._issue("repeated_words", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Adjacent repeated word in '{bullet[:70]}'", sid))
                if re.search(r"(.{8,80})\s+\1(?:\s|[.!?]|$)", bullet, re.IGNORECASE):
                    issues.append(cls._issue("double_sentence", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Repeated phrase in '{bullet[:70]}'", sid))
                if re.search(r"\s{2,}", bullet) or "\t" in bullet:
                    issues.append(cls._issue("broken_spacing", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, "Bullet contains malformed spacing", sid))
                letters = [c for c in bullet if c.isalpha()]
                if len(letters) >= 18 and sum(c.isupper() for c in letters) / len(letters) > 0.75:
                    issues.append(cls._issue("excessive_caps", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, "Body copy uses excessive all-caps text", sid))
                if re.search(r"[!?.,]{2,}", bullet):
                    issues.append(cls._issue("excessive_punctuation", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, "Body copy contains repeated punctuation", sid))
                if len(bullet.split()) < 3:
                    issues.append(cls._issue("orphan_fragment", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, f"Very short bullet fragment: '{bullet}'", sid))
                if re.search(r"\b(?:Tapestry of the Past|Exploring Society|LET[’']?S EXPLORE|DON[’']?T MISS OUT|THINK ABOUT IT|Reprint 20\d{2})\b", bullet, re.IGNORECASE):
                    issues.append(cls._issue("speaker_note_leak", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Source header or classroom instruction leaked into body: '{bullet[:60]}'", sid))
                if len(bullet.split()) >= 7 and re.search(r"\b(?:a|an|the|of|to|from|with|and|or|that|which|who|their|his|her|its|as|by)\s*$", bullet, re.IGNORECASE):
                    issues.append(cls._issue("orphan_fragment", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, f"Bullet appears cut off mid-thought: '{bullet[:70]}'", sid))
                if re.search(r"\b(presenter|speaker|designer|add image|insert chart)\b", bullet, re.IGNORECASE):
                    issues.append(cls._issue("speaker_note_leak", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Presenter or production instruction appears in body: '{bullet[:60]}'", sid))
                if re.search(r"\b(source|citation)\s*:\s*(?:n/?a|tbd|unknown)?\s*$", bullet, re.IGNORECASE):
                    issues.append(cls._issue("citation_incomplete", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, "Visible citation is incomplete", sid, auto_fixable=False))
                if re.search(r"\b(best|only|always|never|guaranteed|unmatched|world[- ]class)\b", bullet, re.IGNORECASE) and not re.search(r"\b(source|survey|according|reported)\b", body, re.IGNORECASE):
                    issues.append(cls._issue("unsupported_superlative", ValidationSeverity.LOW, ValidationCategory.CONTENT, idx, f"Potentially unsupported absolute claim: '{bullet[:60]}'", sid, auto_fixable=False))
                if any(marker in bullet.lower() for marker in _PLACEHOLDERS):
                    issues.append(cls._issue("placeholder_copy", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, "Body contains placeholder copy", sid))
                if "�" in bullet or "â€" in bullet or "Â·" in bullet:
                    issues.append(cls._issue("encoding_artifact", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, "Body contains an encoding artifact", sid))
                if ":" in bullet:
                    lead = _normalized(bullet.split(":", 1)[0])
                    if len(lead) >= 5:
                        lead_slides[lead].add(idx)

            takeaway = _clean(slide.takeaway)
            if takeaway and (any(_similar(takeaway, b) >= 0.88 for b in body_parts) or _similar(takeaway, title) >= 0.9):
                issues.append(cls._issue("duplicate_takeaway", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, idx, "Takeaway repeats the title or a bullet", sid))
            if len(body.split()) >= 12:
                for prev_idx, prev_body in seen_bodies:
                    if _similar(body, prev_body) >= 0.92:
                        issues.append(cls._issue("repeated_slide_copy", ValidationSeverity.HIGH, ValidationCategory.CONTENT, idx, f"Body copy substantially duplicates Slide {prev_idx}", sid))
                        break
                seen_bodies.append((idx, body))
            if idx > 1 and layout not in _INTENTIONAL_SPARSE and len(body.split()) < 12 and not (slide.chart_spec or slide.table_spec or slide.diagram_spec or slide.metrics):
                issues.append(cls._issue("sparse_slide", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Non-divider slide contains fewer than 12 words of supporting content", sid))
            if len(body.split()) > 180:
                issues.append(cls._issue("crowded_slide", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, f"Slide contains {len(body.split())} body words", sid))

        threshold = max(3, len(slides) // 3)
        for lead, positions in lead_slides.items():
            if len(positions) >= threshold:
                first = min(positions)
                issues.append(cls._issue("boilerplate_lead", ValidationSeverity.MEDIUM, ValidationCategory.CONTENT, first, f"Lead phrase '{lead}' repeats on Slides {sorted(positions)}", slides[first - 1].slide_id))

    @classmethod
    def _check_data(cls, slides: list[SlideSpec], issues: list[ValidationIssue]) -> None:
        for idx, slide in enumerate(slides, 1):
            chart = slide.chart_spec
            if chart:
                if not chart.categories:
                    issues.append(cls._issue("chart_missing_categories", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Chart has no categories", slide.slide_id))
                if not chart.series:
                    issues.append(cls._issue("chart_missing_series", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Chart has no series", slide.slide_id))
                for series in chart.series:
                    values = series.get("values", []) if isinstance(series, dict) else []
                    if chart.categories and len(values) != len(chart.categories):
                        issues.append(cls._issue("chart_length_mismatch", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Chart series length does not match category count", slide.slide_id))
                    if any(not isinstance(v, (int, float)) for v in values):
                        issues.append(cls._issue("chart_non_numeric_value", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Chart contains a non-numeric value", slide.slide_id))
                if not _clean(chart.source_provenance):
                    issues.append(cls._issue("chart_missing_source", ValidationSeverity.LOW, ValidationCategory.DATA, idx, "Chart lacks source provenance", slide.slide_id, auto_fixable=False))
                if not _clean(chart.units) and chart.number_format == "number":
                    issues.append(cls._issue("chart_missing_units", ValidationSeverity.LOW, ValidationCategory.DATA, idx, "Chart does not identify its measurement units", slide.slide_id, auto_fixable=False))
            table = slide.table_spec
            if table:
                if not table.headers:
                    issues.append(cls._issue("table_missing_headers", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Table has no headers", slide.slide_id))
                expected = len(table.headers)
                if expected and any(len(row) != expected for row in table.rows):
                    issues.append(cls._issue("table_ragged_rows", ValidationSeverity.HIGH, ValidationCategory.DATA, idx, "Table rows have inconsistent column counts", slide.slide_id))
                if expected > 6:
                    issues.append(cls._issue("table_too_wide", ValidationSeverity.MEDIUM, ValidationCategory.DATA, idx, f"Table has {expected} columns", slide.slide_id))
                if len(table.rows) > 10:
                    issues.append(cls._issue("table_too_long", ValidationSeverity.MEDIUM, ValidationCategory.DATA, idx, f"Table has {len(table.rows)} rows", slide.slide_id))
            metric_labels: set[str] = set()
            for metric in slide.metrics:
                label = _normalized(metric.get("label", ""))
                value = _clean(metric.get("value", ""))
                key = f"{label}:{_normalized(value)}"
                if key in metric_labels:
                    issues.append(cls._issue("metric_duplicate", ValidationSeverity.MEDIUM, ValidationCategory.DATA, idx, "Metric repeats on the same slide", slide.slide_id))
                metric_labels.add(key)
                if value and not label:
                    issues.append(cls._issue("metric_missing_label", ValidationSeverity.MEDIUM, ValidationCategory.DATA, idx, f"Metric '{value}' has no label", slide.slide_id))

    @classmethod
    def _check_images_and_rhythm(
        cls,
        slides: list[SlideSpec],
        assets: list[AssetMetadata],
        asset_by_id: dict[str, AssetMetadata],
        source_images: dict[str, bytes],
        issues: list[ValidationIssue],
    ) -> None:
        used: dict[str, list[int]] = defaultdict(list)
        hashes: dict[str, list[str]] = defaultdict(list)
        perceptual_hashes: dict[str, list[str]] = defaultdict(list)
        assigned_ids = {slide.image_artifact_id for slide in slides if slide.image_artifact_id}
        for asset in assets:
            digest = asset.sha256
            if not digest and asset.asset_id in source_images:
                digest = hashlib.sha256(source_images[asset.asset_id]).hexdigest()
            if digest:
                hashes[digest].append(asset.asset_id)
            if asset.perceptual_hash:
                perceptual_hashes[asset.perceptual_hash].append(asset.asset_id)

        for idx, slide in enumerate(slides, 1):
            asset_id = slide.image_artifact_id
            if slide.layout_family in _IMAGE_LAYOUTS and not asset_id:
                issues.append(cls._issue("missing_required_image", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, "Image-led layout has no assigned image", slide.slide_id))
            if not asset_id:
                continue
            used[asset_id].append(idx)
            asset = asset_by_id.get(asset_id)
            caption = _clean(slide.image_caption or (asset.caption if asset else ""))
            semantic = " ".join(filter(None, [caption, getattr(asset, "nearby_text", ""), getattr(asset, "semantic_summary", "")]))
            slide_text = " ".join([slide.headline, slide.objective, slide.takeaway, *slide.bullets])
            relevance = ImageMatcher.calculate_relevance(slide_text, semantic)
            if relevance < MIN_SEMANTIC_RELEVANCE:
                issues.append(cls._issue("image_semantic_mismatch", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, f"Image '{asset_id}' has low relevance ({relevance:.1f}) to '{slide.headline[:55]}'", slide.slide_id))
            if not caption:
                issues.append(cls._issue("missing_image_caption", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Image '{asset_id}' has no caption", slide.slide_id))
            elif _normalized(caption) in {"source document image", "documentary reference figure", "documentary asset", "image", "figure"} or re.fullmatch(r"fig(?:ure)?\.?\s*\d+(?:\.\d+)*\.?", caption, re.IGNORECASE):
                issues.append(cls._issue("generic_image_caption", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Image '{asset_id}' has a generic caption", slide.slide_id))
            if asset and asset.quality_score < 0.5:
                issues.append(cls._issue("blurry_image", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, f"Image '{asset_id}' quality score is {asset.quality_score:.2f}", slide.slide_id))
            if asset and asset.width and asset.height and asset.width * asset.height < 160_000:
                issues.append(cls._issue("low_resolution_image", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Image '{asset_id}' is only {asset.width}×{asset.height}px", slide.slide_id))
            unused_scores = [
                ImageMatcher.calculate_relevance(slide_text, f"{a.caption} {a.nearby_text} {a.semantic_summary}")
                for a in assets if a.asset_id != asset_id and a.asset_id not in assigned_ids
            ]
            if unused_scores and max(unused_scores) >= relevance + 3.0:
                issues.append(cls._issue("unused_relevant_image", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "A materially more relevant unused source image is available", slide.slide_id))

        for asset_id, positions in used.items():
            if len(positions) > 1:
                for slide_no in positions[1:]:
                    issues.append(cls._issue("duplicate_image_id", ValidationSeverity.HIGH, ValidationCategory.DESIGN, slide_no, f"Image '{asset_id}' repeats from Slide {positions[0]}", slides[slide_no - 1].slide_id))
        for digest, ids in hashes.items():
            positions = sorted({p for asset_id in ids for p in used.get(asset_id, [])})
            if len(positions) > 1:
                for slide_no in positions[1:]:
                    issues.append(cls._issue("duplicate_image_pixels", ValidationSeverity.HIGH, ValidationCategory.DESIGN, slide_no, f"Image pixels duplicate Slide {positions[0]}", slides[slide_no - 1].slide_id))
        for ids in perceptual_hashes.values():
            positions = sorted({p for asset_id in ids for p in used.get(asset_id, [])})
            if len(positions) > 1:
                for slide_no in positions[1:]:
                    issues.append(cls._issue("near_duplicate_image", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, slide_no, f"Image is visually near-identical to Slide {positions[0]}", slides[slide_no - 1].slide_id))

        if assets and slides:
            image_slides = sum(1 for s in slides if s.image_artifact_id)
            assignable_slides = sum(
                any(
                    ImageMatcher.calculate_relevance(
                        " ".join([slide.headline, slide.objective, slide.takeaway, *slide.bullets]),
                        f"{asset.caption} {asset.nearby_text} {asset.semantic_summary}",
                    ) >= MIN_SEMANTIC_RELEVANCE
                    for asset in assets
                )
                for slide in slides
            )
            expected_visuals = min(max(2, len(slides) // 4), assignable_slides, len(assets))
            if image_slides == 0 and expected_visuals > 0:
                issues.append(cls._issue("no_visuals", ValidationSeverity.HIGH, ValidationCategory.DESIGN, 1, "No available source visual is used", slides[0].slide_id))
            elif len(slides) >= 6 and image_slides < expected_visuals:
                issues.append(cls._issue("sparse_visual_pacing", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, 1, f"Only {image_slides} of {expected_visuals} semantically matchable slides use available images", slides[0].slide_id))

        run = 1
        image_run = 1
        for idx in range(1, len(slides)):
            if slides[idx].layout_family == slides[idx - 1].layout_family:
                run += 1
                if run == 3:
                    issues.append(cls._issue("consecutive_same_layout", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx + 1, f"Layout '{slides[idx].layout_family.value}' appears three times consecutively", slides[idx].slide_id))
            else:
                run = 1
            if slides[idx].layout_family in _IMAGE_LAYOUTS and slides[idx - 1].layout_family in _IMAGE_LAYOUTS:
                image_run += 1
                if image_run == 3:
                    issues.append(cls._issue("consecutive_image_layouts", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx + 1, "Three image-led layouts appear consecutively", slides[idx].slide_id))
            else:
                image_run = 1

        image_count = sum(1 for slide in slides if slide.layout_family in _IMAGE_LAYOUTS)
        if len(slides) >= 6 and image_count / len(slides) > 0.75:
            issues.append(cls._issue("visuals_overused", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, 1, f"{image_count} of {len(slides)} slides use image-led layouts", slides[0].slide_id))
        for idx, slide in enumerate(slides, 1):
            lower = " ".join([slide.headline, slide.objective, *slide.bullets]).lower()
            if slide.chart_spec and slide.layout_family not in {LayoutFamily.CHART_FOCUS, LayoutFamily.CHART_INSIGHT, LayoutFamily.A14_CHART_INSIGHT}:
                issues.append(cls._issue("layout_content_mismatch", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Chart content is not using a chart layout", slide.slide_id))
            if slide.diagram_spec and slide.layout_family not in {LayoutFamily.PROCESS_STEPS, LayoutFamily.ARCHITECTURE_DIAGRAM, LayoutFamily.MATRIX_QUADRANT}:
                issues.append(cls._issue("diagram_missing_for_process", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Diagram content is not using a diagram layout", slide.slide_id))
            if not slide.chart_spec and len(re.findall(r"\b\d+(?:\.\d+)?%?\b", lower)) >= 4:
                issues.append(cls._issue("chart_missing_for_numeric_story", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, "Slide contains four or more numeric values without a chart", slide.slide_id, auto_fixable=False))
            if not slide.diagram_spec and re.search(r"\b(step|phase|stage)\s*[1-5]\b", lower):
                issues.append(cls._issue("diagram_missing_for_process", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, "Numbered process content has no process diagram", slide.slide_id, auto_fixable=False))

    @classmethod
    def _check_rendered_pptx(cls, specs: list[SlideSpec], pptx_bytes: bytes, issues: list[ValidationIssue]) -> None:
        try:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE
            prs = Presentation(io.BytesIO(pptx_bytes))
        except Exception as exc:  # noqa: BLE001 - corrupt packages can fail in multiple parser layers
            issues.append(cls._issue("pptx_corrupt", ValidationSeverity.CRITICAL, ValidationCategory.TECHNICAL, 0, f"PPTX cannot be reopened: {exc}", auto_fixable=True))
            return

        if len(prs.slides) != len(specs):
            issues.append(cls._issue("slide_count_mismatch", ValidationSeverity.HIGH, ValidationCategory.TECHNICAL, 0, f"Expected {len(specs)} slides; rendered {len(prs.slides)}"))
        slide_w, slide_h = int(prs.slide_width), int(prs.slide_height)
        for idx, slide in enumerate(prs.slides, 1):
            spec = specs[idx - 1] if idx <= len(specs) else None
            font_sizes: list[float] = []
            body_sizes: list[float] = []
            title_sizes: list[float] = []
            bold_chars = 0
            total_chars = 0
            font_names: set[str] = set()
            meaningful_boxes: list[tuple[int, int, int, int]] = []
            text_boxes: list[tuple[int, int, int, int, str]] = []
            picture_boxes: list[tuple[int, int, int, int]] = []
            has_page = False
            decorative_count = 0
            evidence_card_heights: dict[str, int] = {}
            evidence_text_metrics: dict[str, tuple[int, list[float]]] = {}
            for shape in slide.shapes:
                name = (shape.name or "").lower()
                if match := re.fullmatch(r"evidence-card-(\d+)", name):
                    evidence_card_heights[match.group(1)] = int(shape.height)
                if match := re.fullmatch(r"evidence-text-(\d+)", name):
                    evidence_text_metrics[match.group(1)] = (int(shape.height), [])
                decorative = any(tag in name for tag in ("accent", "backdrop", "background", "page-pill", "photo-container", "photo-mat", "image-frame", "card", "chip", "disc"))
                decorative_count += int(decorative)
                outside = shape.left < -1000 or shape.top < -1000 or shape.left + shape.width > slide_w + 1000 or shape.top + shape.height > slide_h + 1000
                intentional_bleed = any(tag in name for tag in ("bleed", "accent-circle", "corner-accent", "backdrop"))
                if outside and not intentional_bleed:
                    issues.append(cls._issue("off_canvas", ValidationSeverity.HIGH, ValidationCategory.GEOMETRY, idx, f"Shape '{shape.name}' extends outside the canvas", spec.slide_id if spec else ""))
                if getattr(shape, "has_text_frame", False):
                    text = _clean(shape.text)
                    if text == str(idx):
                        has_page = True
                    if text and shape.top < int(slide_h * 0.91) and not decorative:
                        meaningful_boxes.append((shape.left, shape.top, shape.width, shape.height))
                        text_boxes.append((shape.left, shape.top, shape.width, shape.height, text))
                        if shape.left < int(slide_w * 0.025) or shape.left + shape.width > int(slide_w * 0.975):
                            issues.append(cls._issue("margin_violation", ValidationSeverity.LOW, ValidationCategory.GEOMETRY, idx, f"Text '{text[:35]}' enters the horizontal safe margin", spec.slide_id if spec else ""))
                        if shape.top + shape.height > int(slide_h * 0.94):
                            issues.append(cls._issue("footer_collision", ValidationSeverity.MEDIUM, ValidationCategory.GEOMETRY, idx, f"Text '{text[:35]}' enters the footer zone", spec.slide_id if spec else ""))
                    for paragraph in shape.text_frame.paragraphs:
                        for run in paragraph.runs:
                            run_chars = len(run.text or "")
                            total_chars += run_chars
                            if run.font.bold:
                                bold_chars += run_chars
                            if run.font.size:
                                size = float(run.font.size.pt)
                                if match := re.fullmatch(r"evidence-text-(\d+)", name):
                                    evidence_text_metrics[match.group(1)][1].append(size)
                                font_sizes.append(size)
                                is_title = 0.08 * slide_h <= shape.top <= 0.25 * slide_h and size >= 16
                                is_footer = shape.top >= int(slide_h * 0.9)
                                if is_title:
                                    title_sizes.append(size)
                                    if size < 22:
                                        issues.append(cls._issue("title_font_too_small", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, f"Title text renders at {size:g}pt", spec.slide_id if spec else ""))
                                elif text and not is_footer and not decorative and shape.top >= int(slide_h * 0.08):
                                    body_sizes.append(size)
                                if text and not is_footer and not decorative and not is_title and shape.top >= int(slide_h * 0.08) and size < 11.0:
                                    issues.append(cls._issue("body_font_too_small", ValidationSeverity.HIGH, ValidationCategory.DESIGN, idx, f"Text '{text[:45]}' renders at {size:g}pt", spec.slide_id if spec else ""))
                                if is_footer and size < 9:
                                    issues.append(cls._issue("footer_font_too_small", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Footer renders at {size:g}pt", spec.slide_id if spec else ""))
                            if run.font.name:
                                font_names.add(run.font.name)
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    meaningful_boxes.append((shape.left, shape.top, shape.width, shape.height))
                    picture_boxes.append((shape.left, shape.top, shape.width, shape.height))
                    try:
                        source_ratio = shape.image.size[0] / max(1, shape.image.size[1])
                        displayed_ratio = shape.width / max(1, shape.height)
                        cropped = any(float(getattr(shape, attr, 0) or 0) > 0.01 for attr in ("crop_left", "crop_right", "crop_top", "crop_bottom"))
                        if not cropped and abs(displayed_ratio / source_ratio - 1.0) > 0.18:
                            issues.append(cls._issue("stretched_image", ValidationSeverity.HIGH, ValidationCategory.GEOMETRY, idx, "Rendered image aspect ratio is distorted", spec.slide_id if spec else ""))
                        if sum(float(getattr(shape, attr, 0) or 0) for attr in ("crop_left", "crop_right", "crop_top", "crop_bottom")) > 0.75:
                            issues.append(cls._issue("extreme_crop", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "More than 75% aggregate crop is applied to an image", spec.slide_id if spec else ""))
                    except Exception as exc:  # noqa: BLE001 - some linked picture types expose no crop metadata
                        logger.debug("Could not inspect picture geometry on Slide %s: %s", idx, exc)
            if not has_page:
                issues.append(cls._issue("missing_page_number", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Rendered slide has no page number", spec.slide_id if spec else ""))
            if len(font_names) > 3:
                issues.append(cls._issue("too_many_fonts", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Slide uses {len(font_names)} font families", spec.slide_id if spec else ""))
            unsafe = sorted(name for name in font_names if name.lower() not in _SAFE_FONTS)
            if unsafe:
                issues.append(cls._issue("unsafe_font", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Unsafe font(s): {', '.join(unsafe)}", spec.slide_id if spec else ""))
            if body_sizes and max(body_sizes) - min(body_sizes) > 7:
                issues.append(cls._issue("inconsistent_body_size", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, f"Body sizes range from {min(body_sizes):g}pt to {max(body_sizes):g}pt", spec.slide_id if spec else ""))
            if total_chars >= 80 and bold_chars / total_chars > 0.7:
                issues.append(cls._issue("overbold_body", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, "More than 70% of rendered copy is bold", spec.slide_id if spec else ""))
            if decorative_count > 24:
                issues.append(cls._issue("decorative_overload", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Slide contains {decorative_count} decorative objects", spec.slide_id if spec else ""))
            for card_id, (text_height, sizes) in evidence_text_metrics.items():
                card_height = evidence_card_heights.get(card_id, 0)
                if card_height and sizes and min(sizes) < 17:
                    utilization = text_height / card_height
                    issues.append(cls._issue(
                        "excessive_card_padding",
                        ValidationSeverity.MEDIUM,
                        ValidationCategory.DESIGN,
                        idx,
                        f"Evidence card {card_id} uses {min(sizes):g}pt text across only {utilization:.0%} of its height",
                        spec.slide_id if spec else "",
                    ))

            # Text-to-text and text-to-image collision detection. Small edge
            # contacts are ignored to avoid flagging intentional alignment.
            for box_idx, a in enumerate(text_boxes):
                for b in text_boxes[box_idx + 1:]:
                    overlap = cls._overlap_ratio(a[:4], b[:4])
                    if overlap > 0.18:
                        issues.append(cls._issue("shape_overlap", ValidationSeverity.HIGH, ValidationCategory.GEOMETRY, idx, f"Text boxes overlap: '{a[4][:25]}' and '{b[4][:25]}'", spec.slide_id if spec else ""))
                        break
                for picture in picture_boxes:
                    if cls._overlap_ratio(a[:4], picture) > 0.12:
                        issues.append(cls._issue("text_image_overlap", ValidationSeverity.HIGH, ValidationCategory.GEOMETRY, idx, f"Text overlaps an image: '{a[4][:35]}'", spec.slide_id if spec else ""))
                        break

            if spec and spec.layout_family not in _INTENTIONAL_SPARSE and meaningful_boxes:
                left = min(x for x, _y, _w, _h in meaningful_boxes)
                top = min(y for _x, y, _w, _h in meaningful_boxes)
                right = max(x + w for x, _y, w, _h in meaningful_boxes)
                bottom = max(y + h for _x, y, _w, h in meaningful_boxes)
                coverage = ((right - left) * (bottom - top)) / max(1, slide_w * slide_h)
                if coverage < 0.22:
                    issues.append(cls._issue("excessive_blank_space", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, f"Meaningful content spans only {coverage:.0%} of the canvas", spec.slide_id))
                center_x = (left + right) / 2 / slide_w
                center_y = (top + bottom) / 2 / slide_h
                if right < slide_w * 0.52:
                    issues.append(cls._issue("blank_right_half", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Right half of the content canvas is empty", spec.slide_id))
                elif left > slide_w * 0.48:
                    issues.append(cls._issue("blank_left_half", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Left half of the content canvas is empty", spec.slide_id))
                if bottom < slide_h * 0.38:
                    issues.append(cls._issue("blank_bottom_band", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, "Lower content band is empty", spec.slide_id))
                if top > slide_h * 0.34:
                    issues.append(cls._issue("blank_top_band", ValidationSeverity.LOW, ValidationCategory.DESIGN, idx, "Upper content band is empty", spec.slide_id))
                if abs(center_x - 0.5) > 0.3 or abs(center_y - 0.53) > 0.32:
                    issues.append(cls._issue("unbalanced_visual_weight", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Rendered content is strongly off-center", spec.slide_id))
                if coverage < 0.3 and (center_x < 0.3 or center_x > 0.7) and (center_y < 0.3 or center_y > 0.7):
                    issues.append(cls._issue("content_clustered_corner", ValidationSeverity.MEDIUM, ValidationCategory.DESIGN, idx, "Content is clustered in one corner", spec.slide_id))

            try:
                notes = _clean(slide.notes_slide.notes_text_frame.text)
                if not notes:
                    issues.append(cls._issue("missing_notes", ValidationSeverity.LOW, ValidationCategory.TECHNICAL, idx, "Slide has no speaker notes", spec.slide_id if spec else ""))
            except Exception:  # noqa: BLE001 - malformed notes XML must become a QA finding
                issues.append(cls._issue("missing_notes", ValidationSeverity.LOW, ValidationCategory.TECHNICAL, idx, "Slide has no accessible speaker notes", spec.slide_id if spec else ""))

        # Reuse package-level integrity checks, mapping legacy issues to stable IDs.
        stream_report = PPTXValidator.validate_pptx_stream(pptx_bytes, len(specs))
        for old in stream_report.issues:
            msg = old.message.lower()
            slug = "slide_count_mismatch" if "slide count" in msg else "off_canvas" if "overflow" in msg else "placeholder_copy"
            old.checkpoint_id = CHECKPOINT_ID_BY_SLUG[slug]
            old.repair_action = CHECKPOINT_BY_ID[old.checkpoint_id].repair_action
            issues.append(old)

    @staticmethod
    def _overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        intersection_w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
        intersection_h = max(0, min(ay + ah, by + bh) - max(ay, by))
        intersection = intersection_w * intersection_h
        return intersection / max(1, min(aw * ah, bw * bh))
