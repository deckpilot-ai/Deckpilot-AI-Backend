"""Stock Image Provider Tool for DeckPilot AI."""

from typing import Any
from app.services.image_provider import ImageProviderService, StockImageResult
from app.schemas.generation_state import AssetMetadata


class ImageProviderTool:
    """Tool wrapper exposing stock image search and retrieval capabilities."""

    @staticmethod
    async def search(
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
        preferred_provider: str = "all",
    ) -> list[StockImageResult]:
        """Search Unsplash and Pexels stock images."""
        return await ImageProviderService.search_images(
            query=query,
            per_page=per_page,
            orientation=orientation,
            preferred_provider=preferred_provider,
        )

    @staticmethod
    async def fetch_and_store_asset(
        project_id: str,
        query: str,
        preferred_provider: str = "all",
        orientation: str = "landscape",
    ) -> tuple[str, bytes, AssetMetadata] | None:
        """Download and store a stock image into the project storage."""
        return await ImageProviderService.fetch_and_store_stock_asset(
            project_id=project_id,
            query=query,
            preferred_provider=preferred_provider,
            orientation=orientation,
        )

    @staticmethod
    async def fetch_presentation_visuals(
        project_id: str,
        topic: str,
        slide_queries: list[str],
        max_images: int = 4,
    ) -> list[tuple[str, bytes, AssetMetadata]]:
        """Fetch multiple relevant stock images for a presentation topic and slides."""
        return await ImageProviderService.fetch_stock_assets_for_presentation(
            project_id=project_id,
            topic=topic,
            slide_queries=slide_queries,
            max_images=max_images,
        )
