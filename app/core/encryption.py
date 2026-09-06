"""Versioned authenticated encryption for provider credentials at rest."""

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_VERSION_PREFIX = b"DPA2"
_NONCE_BYTES = 12
_ASSOCIATED_DATA = b"deckpilotai:provider-key:v2"


def _get_encryption_key() -> bytes:
    master_secret = settings.key_encryption_secret
    if not master_secret:
        raise ValueError("KEY_ENCRYPTION_SECRET must be configured in environment")
    return hashlib.sha256(master_secret.encode("utf-8")).digest()


def encrypt_secret(plain_text: str) -> bytes:
    """Encrypt a secret with AES-256-GCM and a fresh random nonce."""
    if not plain_text:
        raise ValueError("Secret must not be empty")
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_get_encryption_key()).encrypt(
        nonce,
        plain_text.encode(),
        _ASSOCIATED_DATA,
    )
    return _VERSION_PREFIX + nonce + ciphertext


def is_legacy_encrypted_secret(encrypted_bytes: bytes) -> bool:
    return not encrypted_bytes.startswith(_VERSION_PREFIX)


def _decrypt_legacy_secret(encrypted_bytes: bytes) -> str:
    """Read the original XOR format so stored keys can be rotated in place."""
    if len(encrypted_bytes) < 16:
        raise ValueError("Invalid encrypted data length")
    nonce = encrypted_bytes[:16]
    encrypted_data = encrypted_bytes[16:]
    keystream = hashlib.sha256(_get_encryption_key() + nonce).digest()
    return bytes(byte ^ keystream[index % len(keystream)] for index, byte in enumerate(encrypted_data)).decode()


def decrypt_secret(encrypted_bytes: bytes) -> str:
    """Decrypt a versioned secret, retaining read compatibility for v1 data."""
    if is_legacy_encrypted_secret(encrypted_bytes):
        return _decrypt_legacy_secret(encrypted_bytes)
    if len(encrypted_bytes) < len(_VERSION_PREFIX) + _NONCE_BYTES + 16:
        raise ValueError("Invalid encrypted data length")
    offset = len(_VERSION_PREFIX)
    nonce = encrypted_bytes[offset : offset + _NONCE_BYTES]
    ciphertext = encrypted_bytes[offset + _NONCE_BYTES :]
    plaintext = AESGCM(_get_encryption_key()).decrypt(nonce, ciphertext, _ASSOCIATED_DATA)
    return plaintext.decode()
