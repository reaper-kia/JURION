import hashlib
import re

from identity_service.infra.hashers.refresh_token import SecureRefreshTokenService


def test_generate_returns_unique_url_safe_tokens() -> None:
    service = SecureRefreshTokenService()

    tokens = {service.generate() for _ in range(10)}

    assert len(tokens) == 10
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", token) for token in tokens)


def test_hash_returns_sha256_hex_digest() -> None:
    service = SecureRefreshTokenService()
    raw_token = "example-refresh-token"

    token_hash = service.hash(raw_token)

    assert token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert len(token_hash) == 64
    assert token_hash != raw_token


def test_hash_is_deterministic() -> None:
    service = SecureRefreshTokenService()
    raw_token = service.generate()

    assert service.hash(raw_token) == service.hash(raw_token)
