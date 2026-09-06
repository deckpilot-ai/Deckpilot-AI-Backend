"""Unit tests for live Cloudflare R2 object storage operations."""

import os
import uuid

import pytest

from app.services.storage import storage_service

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_r2_live_roundtrip():
    """Verify live Cloudflare R2 bucket connection, put_bytes, get_bytes, presigned url, and delete."""
    assert storage_service.use_r2, "Storage service should be configured for live Cloudflare R2"
    assert storage_service.s3_client is not None, "S3 client should be initialized"

    test_id = str(uuid.uuid4())[:8]
    test_key = f"test_runs/live_unit_test_{test_id}.txt"
    test_payload = f"deckpilotAI R2 live test verification payload {test_id}".encode()

    try:
        # 1. Put object
        stored_key = storage_service.put_bytes(test_key, test_payload, "text/plain")
        assert stored_key == test_key

        # 2. Get object
        retrieved_data = storage_service.get_bytes(test_key)
        assert retrieved_data == test_payload

        # 3. Presigned download URL
        presigned_url = storage_service.generate_presigned_download_url(test_key, expires_in=300)
        assert "X-Amz-Signature" in presigned_url or "cloudflarestorage.com" in presigned_url
        assert test_key in presigned_url

    finally:
        # 4. Clean up / Delete object
        storage_service.delete_object(test_key)
