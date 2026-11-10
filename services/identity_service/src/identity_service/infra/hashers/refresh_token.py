import hashlib
import secrets


class SecureRefreshTokenService:
    def generate(self) -> str:
        return secrets.token_urlsafe(32)

    def hash(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
