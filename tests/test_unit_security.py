"""Unit tests for app.core.security and app.core.encryption."""

from datetime import timedelta

import pytest
from cryptography.exceptions import InvalidTag

from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.security import (
    AUTH_COOKIE_NAME,
    COOKIE_PARAMS,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert hashed.startswith("$argon2")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_roundtrip():
    user_id = "user-12345-uuid"
    role = "user"
    token = create_access_token(user_id=user_id, role=role, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_cookie_params():
    assert COOKIE_PARAMS["key"] == AUTH_COOKIE_NAME
    assert COOKIE_PARAMS["httponly"] is True
    assert COOKIE_PARAMS["samesite"] == "lax"
    assert COOKIE_PARAMS["path"] == "/"


def test_encryption_at_rest():
    secret_value = "sk-live-actual-openai-or-groq-api-key-test-12345"
    encrypted_bytes = encrypt_secret(secret_value)
    assert isinstance(encrypted_bytes, bytes)
    assert secret_value.encode() not in encrypted_bytes  # Ensure plaintext is not exposed in ciphertext

    decrypted_value = decrypt_secret(encrypted_bytes)
    assert decrypted_value == secret_value

    tampered = bytearray(encrypted_bytes)
    tampered[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt_secret(bytes(tampered))
