"""Stock image provider service for DeckPilot AI.

Integrates Unsplash and Pexels APIs to search, download, validate, and store
high-quality visual assets for presentation slides when reference documents
or user uploads lack imagery.
"""

import asyncio
import hashlib
import io
import logging
import re
import time
import uuid
from typing import Any, Literal

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.generation_state import AssetMetadata
from app.services.storage import storage_service
from app.tools.image_intelligence import ImageIntelligence

logger = logging.getLogger(__name__)


class StockImageResult(BaseModel):
    """Normalized stock image metadata from external providers."""

    id: str
    provider: Literal["unsplash", "pexels", "pixabay"]
    url: str
    thumbnail_url: str = ""
    description: str = ""
    photographer: str = ""
    photographer_url: str = ""
    width: int = 1920
    height: int = 1080
    aspect_ratio: float = 1.777


class ImageProviderService:
    """Service to search, download, and store stock images from Unsplash, Pexels, and Pixabay."""

    UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
    PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
    PIXABAY_SEARCH_URL = "https://pixabay.com/api/"

    @classmethod
    def clean_search_query(cls, query: str, topic: str = "") -> str:
        """Sanitize and ground presentation slide search queries with overall topic context."""
        slide_stopwords = {
            "slide", "presentation", "deck", "overview", "introduction", "conclusion",
            "agenda", "summary", "takeaway", "key", "points", "bullet", "bullets",
            "table", "chart", "figure", "fig", "chapter", "section", "part", "next",
            "previous", "goal", "objective", "background", "strategy", "analysis",
            "first", "second", "third", "fourth", "fifth"
        }

        topic_clean = re.sub(r"[#*`_~\[\](){}<>!?:;,.\"\']+", " ", topic or "") if topic else ""
        topic_tokens = [
            w for w in topic_clean.split()
            if len(w) >= 3 and w.lower() not in slide_stopwords
        ][:2]

        cleaned_query = re.sub(r"[#*`_~\[\](){}<>!?:;,.\"\']+", " ", query or "") if query else ""
        query_tokens = [
            w for w in cleaned_query.split()
            if len(w) >= 3 and w.lower() not in slide_stopwords
        ]

        topic_tokens_lower = {t.lower() for t in topic_tokens}
        distinct_query_tokens = [
            w for w in query_tokens
            if w.lower() not in topic_tokens_lower
        ][:3]

        grounded_tokens = topic_tokens + distinct_query_tokens
        if not grounded_tokens:
            return " ".join(topic_tokens) if topic_tokens else "presentation background"

        return " ".join(grounded_tokens)

    @classmethod
    def verify_semantic_relevance(cls, candidate_desc: str, topic: str, slide_query: str) -> float:
        """Verifies candidate image alt/description for subject-domain alignment."""
        desc_lower = (candidate_desc or "").lower()
        topic_lower = (topic or "").lower()
        query_lower = (slide_query or "").lower()

        corporate_noise = {"office", "laptop", "handshake", "skyscraper", "suits", "businesswoman", "businessman", "meeting room", "conference table"}
        
        is_non_corporate_topic = any(w in topic_lower for w in (
            "history", "historical", "war", "ancient", "rome", "maratha", "empire", "dynasty",
            "health", "medical", "cardiology", "doctor", "patient", "biotech", "pharma",
            "climate", "nature", "forest", "environment", "solar", "space", "astronomy", "art", "craft"
        ))

        if is_non_corporate_topic:
            if any(w in desc_lower for w in corporate_noise):
                return 0.1

        topic_words = set(re.findall(r"\w{4,}", topic_lower))
        query_words = set(re.findall(r"\w{4,}", query_lower))
        desc_words = set(re.findall(r"\w{4,}", desc_lower))

        overlap = len((topic_words | query_words) & desc_words)
        score = min(1.0, 0.4 + (overlap * 0.2))
        return round(score, 2)

    @classmethod
    async def search_unsplash(
        cls,
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
    ) -> list[StockImageResult]:
        """Search stock images from Unsplash API."""
        access_key = settings.unsplash_access_key.strip()
        if not access_key:
            logger.warning("Unsplash access key not configured")
            return []

        search_query = cls.clean_search_query(query)
        headers = {
            "Authorization": f"Client-ID {access_key}",
            "Accept-Version": "v1",
        }
        params: dict[str, Any] = {
            "query": search_query,
            "per_page": max(1, min(per_page, 30)),
            "orientation": orientation if orientation in ("landscape", "portrait", "squarish") else "landscape",
            "content_filter": "high",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.UNSPLASH_SEARCH_URL, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning("Unsplash search HTTP %d: %s", resp.status_code, resp.text[:200])
                    return []

                data = resp.json()
                results: list[StockImageResult] = []
                for item in data.get("results", []):
                    urls = item.get("urls", {})
                    # Prefer regular (~1080p) for fast slide rendering, fallback to full/raw
                    img_url = urls.get("regular") or urls.get("full") or urls.get("raw")
                    if not img_url:
                        continue
                    
                    user = item.get("user", {})
                    w = int(item.get("width") or 1920)
                    h = int(item.get("height") or 1080)
                    desc = (
                        item.get("description")
                        or item.get("alt_description")
                        or f"Photo related to {search_query}"
                    )
                    results.append(
                        StockImageResult(
                            id=f"unsplash_{item.get('id', uuid.uuid4().hex[:8])}",
                            provider="unsplash",
                            url=img_url,
                            thumbnail_url=urls.get("small") or urls.get("thumb", ""),
                            description=desc,
                            photographer=user.get("name") or user.get("username", "Unsplash Contributor"),
                            photographer_url=user.get("links", {}).get("html", "https://unsplash.com"),
                            width=w,
                            height=h,
                            aspect_ratio=round(w / max(1, h), 3),
                        )
                    )
                logger.info("Unsplash search for '%s' returned %d results", search_query, len(results))
                return results
        except Exception as e:
            logger.warning("Unsplash API search error: %s", e)
            return []

    @classmethod
    async def search_pexels(
        cls,
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
    ) -> list[StockImageResult]:
        """Search stock images from Pexels API."""
        api_key = settings.pexels_api_key.strip()
        if not api_key:
            logger.warning("Pexels API key not configured")
            return []

        search_query = cls.clean_search_query(query)
        headers = {
            "Authorization": api_key,
        }
        params: dict[str, Any] = {
            "query": search_query,
            "per_page": max(1, min(per_page, 30)),
            "orientation": orientation if orientation in ("landscape", "portrait", "square") else "landscape",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.PEXELS_SEARCH_URL, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning("Pexels search HTTP %d: %s", resp.status_code, resp.text[:200])
                    return []

                data = resp.json()
                results: list[StockImageResult] = []
                for item in data.get("photos", []):
                    src = item.get("src", {})
                    # Prefer large2x or large for crisp 1080p slide display
                    img_url = src.get("large2x") or src.get("large") or src.get("original")
                    if not img_url:
                        continue
                    
                    w = int(item.get("width") or 1920)
                    h = int(item.get("height") or 1080)
                    desc = item.get("alt") or f"Photo related to {search_query}"
                    results.append(
                        StockImageResult(
                            id=f"pexels_{item.get('id', uuid.uuid4().hex[:8])}",
                            provider="pexels",
                            url=img_url,
                            thumbnail_url=src.get("medium") or src.get("small", ""),
                            description=desc,
                            photographer=item.get("photographer", "Pexels Contributor"),
                            photographer_url=item.get("photographer_url", "https://pexels.com"),
                            width=w,
                            height=h,
                            aspect_ratio=round(w / max(1, h), 3),
                        )
                    )
                logger.info("Pexels search for '%s' returned %d results", search_query, len(results))
                return results
        except Exception as e:
            logger.warning("Pexels API search error: %s", e)
            return []

    @classmethod
    async def search_pixabay(
        cls,
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
    ) -> list[StockImageResult]:
        """Search stock images from Pixabay API."""
        api_key = settings.pixabay_api_key.strip()
        if not api_key:
            logger.warning("Pixabay API key not configured")
            return []

        search_query = cls.clean_search_query(query)
        pix_orientation = "horizontal" if orientation == "landscape" else "all"
        params: dict[str, Any] = {
            "key": api_key,
            "q": search_query,
            "image_type": "photo",
            "orientation": pix_orientation,
            "per_page": max(3, min(per_page, 30)),
            "safesearch": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.PIXABAY_SEARCH_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("Pixabay search HTTP %d: %s", resp.status_code, resp.text[:200])
                    return []

                data = resp.json()
                results: list[StockImageResult] = []
                for item in data.get("hits", []):
                    img_url = item.get("largeImageURL") or item.get("webformatURL") or item.get("previewURL")
                    if not img_url:
                        continue
                    
                    w = int(item.get("imageWidth") or 1920)
                    h = int(item.get("imageHeight") or 1080)
                    desc = item.get("tags") or item.get("type") or f"Photo related to {search_query}"
                    results.append(
                        StockImageResult(
                            id=f"pixabay_{item.get('id', uuid.uuid4().hex[:8])}",
                            provider="pixabay",
                            url=img_url,
                            thumbnail_url=item.get("previewURL") or item.get("webformatURL", ""),
                            description=desc,
                            photographer=item.get("user", "Pixabay Contributor"),
                            photographer_url=item.get("pageURL", "https://pixabay.com"),
                            width=w,
                            height=h,
                            aspect_ratio=round(w / max(1, h), 3),
                        )
                    )
                logger.info("Pixabay search for '%s' returned %d results", search_query, len(results))
                return results
        except Exception as e:
            logger.warning("Pixabay API search error: %s", e)
            return []

    @classmethod
    async def search_images(
        cls,
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
        preferred_provider: str = "all",
    ) -> list[StockImageResult]:
        """Search stock images across Unsplash, Pexels, and Pixabay with automatic fallback & interleaving."""
        if preferred_provider == "unsplash":
            results = await cls.search_unsplash(query, per_page, orientation)
            if not results:
                results = await cls.search_pexels(query, per_page, orientation)
            if not results:
                results = await cls.search_pixabay(query, per_page, orientation)
            return results

        if preferred_provider == "pexels":
            results = await cls.search_pexels(query, per_page, orientation)
            if not results:
                results = await cls.search_unsplash(query, per_page, orientation)
            if not results:
                results = await cls.search_pixabay(query, per_page, orientation)
            return results

        if preferred_provider == "pixabay":
            results = await cls.search_pixabay(query, per_page, orientation)
            if not results:
                results = await cls.search_unsplash(query, per_page, orientation)
            if not results:
                results = await cls.search_pexels(query, per_page, orientation)
            return results

        # Preferred "all": query Unsplash, Pexels, and Pixabay concurrently
        unsplash_task = asyncio.create_task(cls.search_unsplash(query, per_page, orientation))
        pexels_task = asyncio.create_task(cls.search_pexels(query, per_page, orientation))
        pixabay_task = asyncio.create_task(cls.search_pixabay(query, per_page, orientation))
        
        u_res, p_res, px_res = await asyncio.gather(unsplash_task, pexels_task, pixabay_task, return_exceptions=True)
        
        u_list = u_res if isinstance(u_res, list) else []
        p_list = p_res if isinstance(p_res, list) else []
        px_list = px_res if isinstance(px_res, list) else []

        combined: list[StockImageResult] = []
        # Interleave results from all 3 stock providers for diversity
        max_len = max(len(u_list), len(p_list), len(px_list))
        for i in range(max_len):
            if i < len(u_list):
                combined.append(u_list[i])
            if i < len(p_list):
                combined.append(p_list[i])
            if i < len(px_list):
                combined.append(px_list[i])

        return combined[:per_page]

    @classmethod
    async def download_image_bytes(cls, image_url: str, timeout: float = 15.0) -> bytes | None:
        """Download raw image bytes with timeout and size cap."""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(image_url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    return resp.content
                logger.warning("Download image failed HTTP %d (size=%d)", resp.status_code, len(resp.content))
                return None
        except Exception as e:
            logger.warning("Error downloading image from %s: %s", image_url[:60], e)
            return None

    @classmethod
    async def fetch_and_store_stock_asset(
        cls,
        project_id: str,
        query: str,
        topic: str = "",
        preferred_provider: str = "all",
        orientation: str = "landscape",
    ) -> tuple[str, bytes, AssetMetadata] | None:
        """Search, download, validate, and store a stock image asset into StorageService.
        
        Returns:
            (asset_id, image_bytes, AssetMetadata) or None if search/download fails.
        """
        candidates = await cls.search_images(
            query=query,
            per_page=4,
            orientation=orientation,
            preferred_provider=preferred_provider,
        )
        if not candidates:
            logger.info("No stock images found for query '%s'", query)
            return None

        for candidate in candidates:
            # Semantic relevance check before downloading
            rel_score = cls.verify_semantic_relevance(candidate.description, topic=topic, slide_query=query)
            if rel_score < 0.3:
                logger.info("Stock image candidate %s rejected due to semantic mismatch (score=%.2f, desc='%s')", candidate.id, rel_score, candidate.description[:60])
                continue

            img_bytes = await cls.download_image_bytes(candidate.url)
            if not img_bytes:
                continue

            # Validate quality using ImageIntelligence
            is_valid, q_score, reason = ImageIntelligence.validate_image_quality(img_bytes)
            if not is_valid or q_score < 0.35:
                logger.info("Stock image candidate %s rejected (%s, score=%.2f)", candidate.id, reason, q_score)
                continue

            # Inspect dimensions using PIL
            try:
                with Image.open(io.BytesIO(img_bytes)) as pil_img:
                    w, h = pil_img.size
                    img_format = (pil_img.format or "JPEG").lower()
            except Exception:
                w, h = candidate.width, candidate.height
                img_format = "jpeg"

            sha256_hash = hashlib.sha256(img_bytes).hexdigest()
            asset_id = f"stock_{candidate.provider}_{sha256_hash[:12]}"
            slug = re.sub(r"[^a-zA-Z0-9_-]", "_", query.lower())[:24]
            storage_key = f"stock/images/{sha256_hash[:16]}_{slug}.{img_format}"

            # Put bytes to storage service
            content_type = f"image/{img_format}" if img_format != "jpg" else "image/jpeg"
            await asyncio.to_thread(storage_service.put_bytes, storage_key, img_bytes, content_type)

            caption = (
                f"{candidate.description} (Photo by {candidate.photographer} on {candidate.provider.title()})"
                if candidate.description
                else f"Visual on {query} (via {candidate.provider.title()})"
            )

            meta = AssetMetadata(
                asset_id=asset_id,
                source_file=f"{candidate.provider.title()}: {candidate.photographer}",
                page_number=1,
                width=w,
                height=h,
                aspect_ratio=round(w / max(1, h), 3),
                format=img_format,
                sha256=sha256_hash,
                perceptual_hash=ImageIntelligence.compute_dhash(img_bytes),
                caption=caption,
                nearby_text=f"Stock image for {query}",
                semantic_summary=f"{query}. {candidate.description}",
                quality_score=q_score,
                is_valid_figure=True,
                storage_key=storage_key,
            )

            logger.info(
                "Successfully fetched and stored stock asset '%s' from %s for query '%s' (relevance=%.2f)",
                asset_id, candidate.provider, query, rel_score
            )
            return asset_id, img_bytes, meta

        return None

    @classmethod
    async def fetch_stock_assets_for_presentation(
        cls,
        project_id: str,
        topic: str,
        slide_queries: list[str],
        max_images: int = 4,
    ) -> list[tuple[str, bytes, AssetMetadata]]:
        """Fetch multiple distinct stock images for slides in a presentation."""
        fetched_assets: list[tuple[str, bytes, AssetMetadata]] = []
        seen_queries: set[str] = set()

        # Build list of queries (slide-specific queries grounded with presentation topic)
        candidate_queries: list[str] = []
        for q in slide_queries:
            clean = cls.clean_search_query(q, topic=topic)
            if clean and clean not in seen_queries:
                seen_queries.add(clean)
                candidate_queries.append(clean)

        if len(candidate_queries) < max_images and topic:
            clean_topic = cls.clean_search_query(topic)
            for modifier in ["", "concept", "technology", "industry", "future"]:
                combined = f"{clean_topic} {modifier}".strip()
                if combined not in seen_queries:
                    seen_queries.add(combined)
                    candidate_queries.append(combined)

        for query in candidate_queries:
            if len(fetched_assets) >= max_images:
                break
            try:
                res = await cls.fetch_and_store_stock_asset(
                    project_id=project_id,
                    query=query,
                    topic=topic,
                    preferred_provider="all",
                    orientation="landscape",
                )
                if res:
                    fetched_assets.append(res)
            except Exception as e:
                logger.warning("Error fetching stock image for query '%s': %s", query, e)

        logger.info(
            "Fetched %d stock assets for presentation on '%s'",
            len(fetched_assets), topic
        )
        return fetched_assets
