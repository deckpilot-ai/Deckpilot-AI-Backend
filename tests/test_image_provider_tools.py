"""Tests for Unsplash and Pexels stock image provider tools and storage integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.image_provider import ImageProviderService, StockImageResult
from app.tools.image_provider_tool import ImageProviderTool
from app.services.reasoning_engine import ReasoningEngine
from app.core.config import settings


@pytest.mark.asyncio
async def test_unsplash_search_real_api():
    """Verify Unsplash API search returns valid stock images with configured API key."""
    results = await ImageProviderService.search_unsplash(query="renewable energy solar", per_page=2)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0].provider == "unsplash"
    assert results[0].url.startswith("http")
    assert results[0].photographer != ""


@pytest.mark.asyncio
async def test_pexels_search_real_api():
    """Verify Pexels API search returns valid stock images with configured API key."""
    results = await ImageProviderService.search_pexels(query="artificial intelligence", per_page=2)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0].provider == "pexels"
    assert results[0].url.startswith("http")
    assert results[0].photographer != ""


@pytest.mark.asyncio
async def test_combined_search_with_fallback():
    """Verify search_images successfully combines results from available providers."""
    results = await ImageProviderService.search_images(
        query="data science analytics",
        per_page=4,
        preferred_provider="all",
    )
    assert isinstance(results, list)
    assert len(results) >= 1
    providers = {r.provider for r in results}
    # At least one or both providers present
    assert "unsplash" in providers or "pexels" in providers


@pytest.mark.asyncio
async def test_image_provider_tool_wrapper():
    """Verify the ImageProviderTool static interface works seamlessly."""
    results = await ImageProviderTool.search("cloud computing infrastructure", per_page=2)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert hasattr(results[0], "url")


@pytest.mark.asyncio
async def test_fetch_and_store_stock_asset_lifecycle():
    """Verify search -> download -> validate -> store pipeline produces valid AssetMetadata."""
    res = await ImageProviderService.fetch_and_store_stock_asset(
        project_id="test-proj-123",
        query="business team collaboration",
        preferred_provider="all",
    )
    assert res is not None
    asset_id, img_bytes, meta = res
    assert asset_id.startswith("stock_")
    assert len(img_bytes) > 5000
    assert meta.storage_key.startswith("stock/images/")
    assert meta.width > 0
    assert meta.height > 0
    assert meta.quality_score >= 0.35


@pytest.mark.asyncio
async def test_reasoning_engine_selects_stock_image_tool():
    """Verify ReasoningEngine routes queries asking for stock photos to fetch_stock_images_tool."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = MagicMock(
        version=1,
        deck_json_artifact_id="art-1",
        status="ready",
    )
    mock_db.get.return_value = MagicMock(
        json_data='{"slides": [{"title": "Overview", "headline": "Intro"}, {"title": "Market", "headline": "Market Trends"}, {"title": "Summary", "headline": "Key Points"}]}'
    )

    state = await ReasoningEngine.reason_and_route(
        db=mock_db,
        project_id="test-proj",
        user_id="test-user",
        content="find high quality images from unsplash for slide 2",
        mode="autopilot",
    )
    assert state["selected_tool"] == "fetch_stock_images_tool"
    assert state["should_generate"] is True
    assert state["targeted_slide_indices"] == [1]
