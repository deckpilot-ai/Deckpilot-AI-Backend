"""Tests for outbound AI provider URL controls."""

import pytest

from app.core.network_security import validate_provider_base_url


@pytest.mark.parametrize(
    "url",
    [
        "http://openrouter.ai/api/v1",
        "https://127.0.0.1/api/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://openrouter.ai:8443/api/v1",
        "https://user:password@openrouter.ai/api/v1",
        "https://openrouter.ai/api/v1?redirect=http://localhost",
        "https://example.com/api/v1",
    ],
)
def test_provider_url_rejects_ssrf_and_unapproved_hosts(url: str):
    with pytest.raises(ValueError):
        validate_provider_base_url(url)


def test_provider_url_accepts_allowlisted_https_endpoint():
    assert validate_provider_base_url("https://openrouter.ai/api/v1/") == "https://openrouter.ai/api/v1"
