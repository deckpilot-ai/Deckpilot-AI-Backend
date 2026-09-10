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

        # Calculate score matrix (slide_idx, asset_idx) -> score
        scored_pairs = []
        for s_idx, slide in enumerate(slides):
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

        assigned_slides = set()
        assigned_assets = set()

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

        # If Slide 1 (Cover) has no image and a general title hero asset exists, assign the best remaining hero image
        if 0 not in assigned_slides and assets_list:
            unused_assets = [a for i, a in enumerate(assets_list) if i not in assigned_assets]
            if unused_assets:
                cover_asset = unused_assets[0]
                slide0 = slides[0]
                if isinstance(slide0, SlideSpec):
                    slide0.image_artifact_id = cover_asset["id"]
                    slide0.image_caption = cover_asset["caption"]
                else:
                    slide0["imageArtifactId"] = cover_asset["id"]
                    slide0["imageCaption"] = cover_asset["caption"]
                assigned_slides.add(0)
                logger.info("Assigned cover asset '%s' to Slide 1", cover_asset['id'])
