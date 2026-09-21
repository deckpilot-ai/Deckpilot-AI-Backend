"""Semantic Image-to-Slide Matcher for DeckPilot AI.

Matches documentary visual assets to slides based on semantic keyword overlap,
caption provenance, and entity alignment, dynamically distributing visuals across
the presentation to achieve an optimal visual pacing ratio.
"""

import logging
import re
from typing import Any

from app.schemas.generation_state import (
    AssetMetadata,
    LayoutFamily,
    SlideSpec,
    normalize_bullet_items,
)

logger = logging.getLogger(__name__)

MIN_SEMANTIC_RELEVANCE = 1.5

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "fig", "figure", "photo", "plate", "image", "source", "reference", "study",
    "chapter", "section", "part", "detail", "notice", "that", "this", "these",
    "presentation", "deck", "slide",
}


import unicodedata


def tokenize(text: str) -> set[str]:
    """Tokenize and stem basic alphanumeric terms with unicode diacritic folding."""
    norm = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    clean = re.sub(r"[^\w\s]", " ", norm.lower())
    words = clean.split()
    tokens = set()
    for w in words:
        if len(w) >= 3 and w not in STOPWORDS:
            # Simple stemming
            if w.endswith("s") and len(w) > 4:
                w = w[:-1]
            tokens.add(w)
    return tokens


class ImageMatcher:
    """Matches slides to the most relevant documentary image assets with dynamic pacing."""

    @classmethod
    def calculate_relevance(
        cls,
        slide_text: str,
        caption: str,
        topic_context: str = "",
        slide_section: str = "",
        image_section: str = "",
        image_type: str = "",
    ) -> float:
        """Calculate relevance score between slide text, section provenance, and image metadata."""
        caption_lower = (caption or "").lower()
        topic_lower = (topic_context or "").lower()
        slide_lower = (slide_text or "").lower()

        # Reject corporate stock photos for non-corporate subjects
        corporate_noise = {"office", "laptop", "handshake", "skyscraper", "suits", "businesswoman", "businessman", "meeting room", "conference table"}
        is_non_corporate_topic = any(w in topic_lower for w in (
            "history", "historical", "war", "ancient", "rome", "maratha", "empire", "dynasty",
            "health", "medical", "cardiology", "doctor", "patient", "biotech", "pharma",
            "climate", "nature", "forest", "environment", "solar", "space", "astronomy", "art", "craft",
            "constitution", "parliament", "democracy", "civics"
        ))
        if is_non_corporate_topic and any(w in caption_lower for w in corporate_noise):
            return 0.0

        slide_tokens = tokenize(slide_text)
        caption_tokens = tokenize(caption)

        if not slide_tokens and not caption_tokens:
            return 0.0

        score = 0.0

        # 1. Section Provenance Preservation (+4.0 bonus if from identical source section)
        if slide_section and image_section:
            sec_slide_tokens = tokenize(slide_section)
            sec_img_tokens = tokenize(image_section)
            if sec_slide_tokens & sec_img_tokens:
                score += 4.0

        # 2. Image Type to Slide Intent Matching
        if image_type == "map" and any(w in slide_lower for w in ("map", "territory", "boundary", "expansion", "region", "geography", "timeline")):
            score += 3.5
        elif image_type == "portrait" and any(w in slide_lower for w in ("leader", "biography", "minister", "president", "shastri", "vajpayee", "ruler", "architect", "figure", "founder")):
            score += 3.5
        elif image_type == "diagram" and any(w in slide_lower for w in ("structure", "system", "parliament", "chambers", "bicameral", "houses", "framework", "composition")):
            score += 3.0
        elif image_type == "chart" and any(w in slide_lower for w in ("seats", "representation", "numbers", "data", "statistics", "percentage", "population")):
            score += 3.0
        elif image_type in ("artefact", "photograph") and any(w in slide_lower for w in ("sadan", "bhavan", "building", "hall", "monument", "constitution", "emblem", "carving", "architecture")):
            score += 2.5

        # 3. Keyword / Entity Token Overlap
        intersection = slide_tokens & caption_tokens
        if not intersection:
            sub_matches = 0
            for st in slide_tokens:
                for ct in caption_tokens:
                    if (st in ct or ct in st) and len(min(st, ct, key=len)) >= 4:
                        sub_matches += 1
            score += sub_matches * 1.5
        else:
            for token in intersection:
                if len(token) >= 6:
                    score += 3.0
                elif len(token) >= 4:
                    score += 2.2
                else:
                    score += 1.0

        return score

    @classmethod
    def assign_images_semantically(
        cls,
        slides: list[SlideSpec] | list[dict[str, Any]],
        available_assets: list[AssetMetadata] | list[dict[str, Any]],
        min_relevance_threshold: float = MIN_SEMANTIC_RELEVANCE,
        topic_context: str = "",
    ) -> None:
        """Assign assets to slides semantically with dynamic visual ratio. Mutates slides in place."""
        if not slides or not available_assets:
            return

        # Normalize assets list
        assets_list: list[dict[str, Any]] = []
        for a in available_assets:
            if isinstance(a, AssetMetadata):
                assets_list.append({
                    "id": a.asset_id,
                    "caption": a.caption or "",
                    "nearby_text": getattr(a, "nearby_text", "") or "",
                    "summary": getattr(a, "semantic_summary", "") or "",
                    "image_type": getattr(a, "image_type", "photograph") or "photograph",
                    "section": getattr(a, "section", "") or "",
                    "quality": getattr(a, "quality_score", 1.0),
                    "key": a.storage_key or "",
                })
            elif isinstance(a, dict):
                assets_list.append({
                    "id": a.get("asset_id") or a.get("id"),
                    "caption": a.get("caption", ""),
                    "nearby_text": a.get("nearby_text", ""),
                    "summary": a.get("semantic_summary", ""),
                    "image_type": a.get("image_type", "photograph"),
                    "section": a.get("section", ""),
                    "quality": float(a.get("quality_score", 1.0)),
                    "key": a.get("storage_key", ""),
                })

        # Filter out very low quality assets if high quality ones exist
        assets_list = [a for a in assets_list if a["quality"] >= 0.4]
        if not assets_list:
            return

        # Dynamic target image allocation count (aim for 40% to 65% of content slides when rich visuals exist)
        total_slides = len(slides)
        target_visual_count = min(len(assets_list), max(1, int((total_slides - 1) * 0.60)))

        assigned_slides: set[int] = set()
        assigned_assets: set[int] = set()
        asset_index_by_id = {asset["id"]: idx for idx, asset in enumerate(assets_list)}

        # 1. Preserve valid explicit assignments
        for s_idx, slide in enumerate(slides):
            existing_id = (
                slide.image_artifact_id
                if isinstance(slide, SlideSpec)
                else slide.get("imageArtifactId") or slide.get("image_artifact_id")
            )
            if existing_id in asset_index_by_id and existing_id not in assigned_assets:
                assigned_slides.add(s_idx)
                assigned_assets.add(asset_index_by_id[existing_id])

        NON_IMAGE_LAYOUTS = {
            "comparison", "table", "chart", "timeline", "metrics", "metrics_grid",
            "kpi", "matrix", "matrix_quadrant", "quote", "dark_quote", "closing"
        }

        def _is_ineligible(s: Any) -> bool:
            if isinstance(s, SlideSpec):
                fam = getattr(s.layout_family, "value", str(s.layout_family or "")).lower()
                hint = str(s.layout_hint or "").lower()
                if fam in ("comparison", "timeline", "table", "chart", "metrics_grid"):
                    return True
                if hint in NON_IMAGE_LAYOUTS:
                    return True
                if s.table_spec or s.chart_spec or s.diagram_spec:
                    return True
                return False
            elif isinstance(s, dict):
                hint = str(s.get("layoutHint") or s.get("layout_hint") or "").lower()
                if hint in NON_IMAGE_LAYOUTS:
                    return True
                if s.get("table") or s.get("chart"):
                    return True
                return False
            return False

        # 2. Score all candidate pairs (slide_idx, asset_idx)
        scored_pairs = []
        for s_idx, slide in enumerate(slides):
            if s_idx in assigned_slides:
                continue
            if _is_ineligible(slide):
                continue

            # Check slide text and section
            if isinstance(slide, SlideSpec):
                slide_section = slide.section or ""
                slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
            else:
                slide_section = slide.get("section", "") or slide.get("chapter", "")
                bullets = normalize_bullet_items(slide.get("bullets"))
                slide["bullets"] = bullets
                slide_text = f"{slide.get('headline', '')} {slide.get('purpose', '')} {slide.get('takeaway', '')} {' '.join(bullets)}"

            for a_idx, asset in enumerate(assets_list):
                if a_idx in assigned_assets:
                    continue
                evidence = f"{asset['caption']} {asset['nearby_text']} {asset['summary']}".strip()
                score = cls.calculate_relevance(
                    slide_text,
                    evidence or asset["caption"],
                    topic_context=topic_context,
                    slide_section=slide_section,
                    image_section=asset["section"],
                    image_type=asset["image_type"],
                )

                pacing_bonus = 0.5 if (s_idx % 2 == 1 or s_idx == 0) else 0.0

                if score >= min_relevance_threshold:
                    scored_pairs.append((score + pacing_bonus, score, s_idx, a_idx))

        # Sort by highest combined relevance score first
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        for _combined, raw_score, s_idx, a_idx in scored_pairs:
            if len(assigned_assets) >= target_visual_count and len(assigned_slides) >= max(2, target_visual_count):
                break

            if s_idx in assigned_slides or a_idx in assigned_assets:
                continue

            asset = assets_list[a_idx]
            slide = slides[s_idx]

            caption = asset["caption"] or asset["summary"] or "Source document visual reference"
            if isinstance(slide, SlideSpec):
                slide.image_artifact_id = asset["id"]
                slide.image_caption = caption
                # Promote layout to image-capable layout if it was a generic two-column or default
                if slide.layout_family in (LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID, LayoutFamily.HERO, LayoutFamily.SECTION_DIVIDER):
                    if s_idx == 0:
                        slide.layout_family = LayoutFamily.HERO
                        slide.archetype_id = "A2"
                    else:
                        slide.layout_family = LayoutFamily.TEXT_IMAGE
                        slide.layout_hint = "text_image"
            else:
                slide["imageArtifactId"] = asset["id"]
                slide["imageCaption"] = caption
                hint = str(slide.get("layoutHint") or slide.get("layout_hint") or "").lower()
                if hint in (None, "", "default", "standard", "two_column", "cards"):
                    slide["layoutHint"] = "text_image" if s_idx > 0 else "hero_visual"

            assigned_slides.add(s_idx)
            assigned_assets.add(a_idx)
            logger.info(
                "Semantically matched Slide %s to asset '%s' (type=%s, score=%.1f, caption='%s')",
                s_idx + 1, asset['id'], asset.get('image_type'), raw_score, caption[:50]
            )

        # 3. Fallback pass: ensure valid extracted images from source are distributed to eligible slides
        if len(assigned_assets) < min(len(assets_list), target_visual_count):
            for a_idx, asset in enumerate(assets_list):
                if a_idx in assigned_assets:
                    continue
                for s_idx, slide in enumerate(slides):
                    if s_idx in assigned_slides or s_idx == 0:
                        continue
                    if _is_ineligible(slide):
                        continue
                    caption = asset["caption"] or asset["summary"] or "Source document visual reference"
                    if isinstance(slide, SlideSpec):
                        if slide.table_spec or slide.chart_spec or slide.diagram_spec:
                            continue
                        slide.image_artifact_id = asset["id"]
                        slide.image_caption = caption
                        if slide.layout_family in (LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID, LayoutFamily.HERO, LayoutFamily.SECTION_DIVIDER):
                            slide.layout_family = LayoutFamily.TEXT_IMAGE
                            slide.layout_hint = "text_image"
                    else:
                        hint = str(slide.get("layoutHint") or slide.get("layout_hint") or "").lower()
                        if hint in ("table", "chart"):
                            continue
                        slide["imageArtifactId"] = asset["id"]
                        slide["imageCaption"] = caption
                        if hint in (None, "", "default", "standard", "two_column", "cards"):
                            slide["layoutHint"] = "text_image"

                    assigned_slides.add(s_idx)
                    assigned_assets.add(a_idx)
                    logger.info("Allocated source asset '%s' to slide %s to fulfill visual coverage", asset['id'], s_idx + 1)
                    break
                if len(assigned_assets) >= target_visual_count:
                    break

    @classmethod
    def rematch_images_semantically(
        cls,
        slides: list[SlideSpec],
        available_assets: list[AssetMetadata],
        min_relevance_threshold: float = MIN_SEMANTIC_RELEVANCE,
        topic_context: str = "",
    ) -> None:
        """Recompute one-to-one assignments for image-capable slides during repair passes."""
        if not slides or not available_assets:
            return

        # Exclude cover if it already has an established hero image
        reserved_asset_ids = {
            slide.image_artifact_id
            for idx, slide in enumerate(slides)
            if idx == 0 and slide.image_artifact_id
        }

        # Clear existing non-cover image assignments so we can re-assign globally
        eligible_slides = []
        for idx, slide in enumerate(slides):
            if idx > 0 and not slide.table_spec and (slide.image_artifact_id or slide.layout_family in (
                LayoutFamily.TEXT_IMAGE, LayoutFamily.IMAGE_FOCUS, LayoutFamily.TWO_COLUMN, LayoutFamily.CARD_GRID,
                LayoutFamily.A2_TITLE_SPLIT, LayoutFamily.A8_STAT_IMAGE_HIGHLIGHT
            )):
                eligible_slides.append((idx, slide))

        pairs: list[tuple[float, int, int]] = []
        for s_idx, slide in eligible_slides:
            slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
            for a_idx, asset in enumerate(available_assets):
                if asset.asset_id in reserved_asset_ids or asset.quality_score < 0.4:
                    continue
                evidence = f"{asset.caption} {asset.nearby_text} {asset.semantic_summary}".strip()
                score = cls.calculate_relevance(slide_text, evidence or asset.caption, topic_context=topic_context)
                if score >= min_relevance_threshold:
                    pairs.append((score, s_idx, a_idx))

        # Reset images for eligible slides
        for _idx, slide in eligible_slides:
            slide.image_artifact_id = None
            slide.image_caption = ""

        used_slides: set[int] = set()
        used_assets: set[int] = set()

        for score, s_idx, a_idx in sorted(pairs, key=lambda x: x[0], reverse=True):
            if s_idx in used_slides or a_idx in used_assets:
                continue
            slide = slides[s_idx]
            asset = available_assets[a_idx]
            slide.image_artifact_id = asset.asset_id
            slide.image_caption = asset.caption or asset.semantic_summary
            slide.layout_family = LayoutFamily.TEXT_IMAGE
            slide.layout_hint = "text_image"
            used_slides.add(s_idx)
            used_assets.add(a_idx)
            logger.info("Rematched Slide %s -> Asset '%s' (score=%.1f)", s_idx + 1, asset.asset_id, score)
