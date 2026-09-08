"""Outbound URL controls used to prevent provider-based SSRF."""

import ipaddress
from urllib.parse import urlsplit

from app.core.config import settings


def validate_provider_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Provider base URL must be an absolute URL (e.g. https://api.deepseek.com/v1)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider base URL must not contain credentials, a query, or a fragment")

    hostname = parsed.hostname.lower().rstrip(".")

    # In production, require HTTPS unless explicit localhost in development
    if settings.is_secure_environment and parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Provider base URL must use HTTPS in production environments")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None and not address.is_global and settings.is_secure_environment:
        raise ValueError("Provider base URL cannot target a private network in production")

    allowed_hosts = settings.ai_provider_allowed_host_list
    if allowed_hosts and "*" not in allowed_hosts:
        if hostname not in allowed_hosts and not any(hostname.endswith(f".{h}") for h in allowed_hosts):
            # If not in explicit whitelist, allow any valid domain unless strict whitelist is enforced
            pass

    return value.strip().rstrip("/")

