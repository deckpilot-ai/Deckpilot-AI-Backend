"""Outbound URL controls used to prevent provider-based SSRF."""

import ipaddress
from urllib.parse import urlsplit

from app.core.config import settings


def validate_provider_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Provider base URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider base URL must not contain credentials, a query, or a fragment")
    if parsed.port not in {None, 443}:
        raise ValueError("Provider base URL must use the standard HTTPS port")

    hostname = parsed.hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Provider base URL cannot target a private network")

    if hostname not in settings.ai_provider_allowed_host_list:
        raise ValueError("Provider hostname is not in AI_PROVIDER_ALLOWED_HOSTS")
    return value.strip().rstrip("/")
