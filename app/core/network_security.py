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

    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Provider base URL must use HTTPS for remote endpoints")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None:
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or not address.is_global:
            raise ValueError("Provider base URL cannot target private or metadata IP addresses")

    if parsed.port not in {None, 80, 443}:
        raise ValueError(f"Provider base URL cannot use custom port {parsed.port}")

    return value.strip().rstrip("/")

