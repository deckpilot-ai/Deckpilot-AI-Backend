"""Semantic Image-to-Slide Matcher for DeckPilot AI.

Matches documentary visual assets to slides based on semantic keyword overlap,
caption provenance, and entity alignment, preventing wrong image assignment.
"""

import logging
import re
from typing import Any

from app.schemas.generation_state import AssetMetadata, SlideSpec

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "fig", "figure", "photo", "plate", "image", "source", "reference", "study",
    "chapter", "section", "part", "detail", "notice", "that", "this", "these",
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
    """Matches slides to the most relevant documentary image assets."""

    @classmethod
    def calculate_relevance(cls, slide_text: str, caption: str) -> float:
        """Calculate relevance score between slide text and image caption."""
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
            # Higher weight for proper nouns / entities
            if len(token) >= 5:
                score += 3.0
            else:
                score += 1.5

        return score

    @classmethod
    def assign_images_semantically(
        cls,
        slides: list[SlideSpec] | list[dict[str, Any]],
        available_assets: list[AssetMetadata] | list[dict[str, Any]],
        min_relevance_threshold: float = 1.5,
    ) -> None:
        """Assign assets to slides semantically. Mutates slides in place."""
        if not slides or not available_assets:
            return

        # Normalize assets
        assets_list = []
        for a in available_assets:
            if isinstance(a, AssetMetadata):
                assets_list.append({"id": a.asset_id, "caption": a.caption or "", "key": a.storage_key or ""})
            elif isinstance(a, dict):
                assets_list.append({
                    "id": a.get("asset_id") or a.get("id"),
                    "caption": a.get("caption", ""),
                    "key": a.get("storage_key", ""),
                })

        # Preserve explicit image choices and reserve those assets. QA will
        # independently remove a choice if its source context is irrelevant.
        assigned_slides: set[int] = set()
        assigned_assets: set[int] = set()
        asset_index_by_id = {asset["id"]: idx for idx, asset in enumerate(assets_list)}
        for s_idx, slide in enumerate(slides):
            existing_id = (
                slide.image_artifact_id
                if isinstance(slide, SlideSpec)
                else slide.get("imageArtifactId") or slide.get("image_artifact_id")
            )
            if existing_id in asset_index_by_id:
                assigned_slides.add(s_idx)
                assigned_assets.add(asset_index_by_id[existing_id])

        # Calculate score matrix (slide_idx, asset_idx) -> score
        scored_pairs = []
        for s_idx, slide in enumerate(slides):
            if s_idx in assigned_slides:
                continue
            if isinstance(slide, SlideSpec):
                image_eligible = slide.layout_family.value in {
                    "hero", "image_focus", "text_image", "A2", "A3", "A8"
                }
            else:
                hint = str(slide.get("layoutHint") or slide.get("layout_hint") or "").lower()
                image_eligible = not hint or hint in {
                    "hero", "hero_visual", "image_focus", "text_image",
                    "image_and_text", "text_and_image", "a2", "a3", "a8",
                }
            if not image_eligible:
                continue
            if isinstance(slide, SlideSpec):
                slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
            else:
                slide_text = f"{slide.get('headline', '')} {slide.get('purpose', '')} {slide.get('takeaway', '')} {' '.join(slide.get('bullets', []))}"

            for a_idx, asset in enumerate(assets_list):
                score = cls.calculate_relevance(slide_text, asset["caption"])
                if score >= min_relevance_threshold:
                    scored_pairs.append((score, s_idx, a_idx))

        # Sort by highest relevance score first (Greedy Assignment)
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        for score, s_idx, a_idx in scored_pairs:
            if s_idx in assigned_slides or a_idx in assigned_assets:
                continue

            asset = assets_list[a_idx]
            slide = slides[s_idx]

            if isinstance(slide, SlideSpec):
                slide.image_artifact_id = asset["id"]
                slide.image_caption = asset["caption"]
            else:
                slide["imageArtifactId"] = asset["id"]
                slide["imageCaption"] = asset["caption"]
                if slide.get("layoutHint") in (None, "default", "two_column"):
                    slide["layoutHint"] = "image_focus"

            assigned_slides.add(s_idx)
            assigned_assets.add(a_idx)
            logger.info("Semantically matched Slide %s to asset '%s' (score=%.1f, caption='%s')", s_idx + 1, asset['id'], score, asset['caption'][:50])

        # Do not force an arbitrary image onto the cover. A cover image is used
        # only when it clears the same semantic threshold as every other slide.

    @classmethod
    def rematch_images_semantically(
        cls,
        slides: list[SlideSpec],
        available_assets: list[AssetMetadata],
        min_relevance_threshold: float = 1.5,
    ) -> None:
        """Recompute one-to-one assignments for existing image-capable slides.

        Unlike ``assign_images_semantically``, this deliberately releases current
        assignments. It is used by the repair loop to avoid slide-by-slide swaps
        that can oscillate between two otherwise suitable assets.
        """
        image_layouts = {"hero", "image_focus", "text_image", "A2", "A3", "A8"}
        reserved_asset_ids = {
            slide.image_artifact_id
            for idx, slide in enumerate(slides)
            if idx == 0 and slide.image_artifact_id
        }
        eligible = [
            (idx, slide)
            for idx, slide in enumerate(slides)
            if idx > 0 and (slide.image_artifact_id or slide.layout_family.value in image_layouts)
        ]
        pairs: list[tuple[float, int, int]] = []
        for slide_idx, slide in eligible:
            slide_text = f"{slide.headline} {slide.objective} {slide.takeaway} {' '.join(slide.bullets or [])}"
            for asset_idx, asset in enumerate(available_assets):
                if asset.asset_id in reserved_asset_ids:
                    continue
                evidence = f"{asset.caption} {asset.nearby_text} {asset.semantic_summary}"
                score = cls.calculate_relevance(slide_text, evidence)
                if score >= min_relevance_threshold and asset.quality_score >= 0.5:
                    pairs.append((score, slide_idx, asset_idx))

        for _idx, slide in eligible:
            slide.image_artifact_id = None
            slide.image_caption = ""

        used_slides: set[int] = set()
        used_assets: set[int] = set()
        for _score, slide_idx, asset_idx in sorted(pairs, reverse=True):
            if slide_idx in used_slides or asset_idx in used_assets:
                continue
            slide = slides[slide_idx]
            asset = available_assets[asset_idx]
            slide.image_artifact_id = asset.asset_id
            slide.image_caption = asset.caption or asset.semantic_summary
            used_slides.add(slide_idx)
            used_assets.add(asset_idx)
