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

MIN_SEMANTIC_RELEVANCE = 4.5

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "fig", "figure", "photo", "plate", "image", "source", "reference", "study",
    "chapter", "section", "part", "detail", "notice", "that", "this", "these",
    "ancient", "empire", "imperial", "india", "indian", "kingdom", "mauryan",
    "region", "ruler", "state", "territory", "presentation", "deck", "slide",
}


def tokenize(text: str) -> set[str]:
    """Tokenize and stem basic alphanumeric terms."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
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
    def calculate_relevance(cls, slide_text: str, caption: str) -> float:
        """Calculate relevance score between slide text and image caption/evidence."""
        slide_tokens = tokenize(slide_text)
        caption_tokens = tokenize(caption)

        if not slide_tokens or not caption_tokens:
            return 0.0

        intersection = slide_tokens & caption_tokens
        if not intersection:
            # Check for substring matches (e.g. "maurya" in "mauryan")
            sub_matches = 0
            for st in slide_tokens:
                for ct in caption_tokens:
                    if (st in ct or ct in st) and len(min(st, ct, key=len)) >= 4:
                        sub_matches += 1
            return sub_matches * 1.5

        # Weight key domain entities higher
        score = 0.0
        for token in intersection:
            if len(token) >= 6:
                score += 3.0
            elif len(token) >= 4:
                score += 2.5
            else:
                score += 1.0

        return score

    @classmethod
    def assign_images_semantically(
        cls,
        slides: list[SlideSpec] | list[dict[str, Any]],
        available_assets: list[AssetMetadata] | list[dict[str, Any]],
        min_relevance_threshold: float = MIN_SEMANTIC_RELEVANCE,
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
                    "quality": getattr(a, "quality_score", 1.0),
                    "key": a.storage_key or "",
                })
            elif isinstance(a, dict):
                assets_list.append({
                    "id": a.get("asset_id") or a.get("id"),
                    "caption": a.get("caption", ""),
                    "nearby_text": a.get("nearby_text", ""),
                    "summary": a.get("semantic_summary", ""),
                    "quality": float(a.get("quality_score", 1.0)),
                    "key": a.get("storage_key", ""),
                })

        # Filter out very low quality assets if high quality ones exist
        assets_list = [a for a in assets_list if a["quality"] >= 0.4]
        if not assets_list:
            return

        # Dynamic target image allocation count (aim for 30% to 50% of content slides)
        total_slides = len(slides)
        target_visual_count = min(len(assets_list), max(1, int((total_slides - 1) * 0.45)))

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

        # 2. Score all candidate pairs (slide_idx, asset_idx)
        scored_pairs = []
        for s_idx, slide in enumerate(slides):
            if s_idx in assigned_slides:
                continue

            # Ineligible slides: explicit non-image layout hints (comparison, table, chart, matrix, timeline)
            if isinstance(slide, SlideSpec):
                if slide.table_spec or slide.chart_spec or slide.diagram_spec:
                    continue
                if slide.layout_family in (LayoutFamily.COMPARISON, LayoutFamily.MATRIX_QUADRANT, LayoutFamily.TIMELINE, LayoutFamily.TABLE_FOCUS, LayoutFamily.CHART_FOCUS):
                    continue
                slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
            else:
                hint = str(slide.get("layoutHint") or slide.get("layout_hint") or "").lower()
                if hint in ("comparison", "table", "table_focus", "chart", "chart_focus", "matrix", "matrix_quadrant", "timeline", "roadmap") or slide.get("table") or slide.get("chart"):
                    continue
                bullets = normalize_bullet_items(slide.get("bullets"))
                slide["bullets"] = bullets
                slide_text = f"{slide.get('headline', '')} {slide.get('purpose', '')} {slide.get('takeaway', '')} {' '.join(bullets)}"

            for a_idx, asset in enumerate(assets_list):
                if a_idx in assigned_assets:
                    continue
                evidence = f"{asset['caption']} {asset['nearby_text']} {asset['summary']}".strip()
                score = cls.calculate_relevance(slide_text, evidence or asset["caption"])

                # Pacing bonus: slightly favor even distribution across chapters
                pacing_bonus = 0.5 if (s_idx % 2 == 1 or s_idx == 0) else 0.0

                if score >= min_relevance_threshold:
                    scored_pairs.append((score + pacing_bonus, score, s_idx, a_idx))

        # Sort by highest combined relevance score first
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        for _combined, raw_score, s_idx, a_idx in scored_pairs:
            if len(assigned_assets) >= target_visual_count and len(assigned_slides) >= max(2, target_visual_count):
                # We reached our optimal ratio
                break

            if s_idx in assigned_slides or a_idx in assigned_assets:
                continue

            # Prevent 2 consecutive slides from getting images if we have few images
            if len(assets_list) < total_slides // 2:
                if (s_idx - 1) in assigned_slides and (s_idx + 1) in assigned_slides:
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
                "Semantically matched Slide %s to asset '%s' (score=%.1f, caption='%s')",
                s_idx + 1, asset['id'], raw_score, caption[:50]
            )

    @classmethod
    def rematch_images_semantically(
        cls,
        slides: list[SlideSpec],
        available_assets: list[AssetMetadata],
        min_relevance_threshold: float = MIN_SEMANTIC_RELEVANCE,
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
                score = cls.calculate_relevance(slide_text, evidence or asset.caption)
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
