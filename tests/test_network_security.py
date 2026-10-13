"""Tests for outbound AI provider URL controls."""

import pytest

from app.core.network_security import validate_provider_base_url
from app.services.provider_router import ProviderRouter


@pytest.mark.parametrize(
    "url",
    [
        "http://openrouter.ai/api/v1",
        "https://127.0.0.1/api/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://openrouter.ai:8443/api/v1",
        "https://user:password@openrouter.ai/api/v1",
        "https://openrouter.ai/api/v1?redirect=http://localhost",
    ],
)
def test_provider_url_rejects_ssrf_and_invalid_hosts(url: str):
    with pytest.raises(ValueError):
        validate_provider_base_url(url)


def test_provider_url_rejects_public_host_outside_allowlist():
    with pytest.raises(ValueError, match="AI_PROVIDER_ALLOWED_HOSTS"):
        validate_provider_base_url("https://unapproved-provider.example/v1")


def test_provider_url_accepts_allowlisted_https_endpoint():
    assert validate_provider_base_url("https://openrouter.ai/api/v1/") == "https://openrouter.ai/api/v1"
    assert validate_provider_base_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1"


@pytest.mark.asyncio
async def test_model_discovery_rejects_unapproved_host_before_network_call():
    with pytest.raises(ValueError, match="AI_PROVIDER_ALLOWED_HOSTS"):
        await ProviderRouter.fetch_provider_models("https://unapproved-provider.example/v1")
