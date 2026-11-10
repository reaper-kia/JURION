from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from gateway.application.core import VerifiedActor

PERMISSIONS = frozenset(
    {"conversations:use", "sources:read", "users:read", "users:block"}
)


class TokenVerifier:
    def __init__(self, key: str, issuer: str, audience: str):
        self.key, self.issuer, self.audience = key, issuer, audience

    def verify(self, token: str, request_id: str) -> VerifiedActor:
        try:
            key = serialization.load_pem_public_key(self.key.encode())
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError("invalid key")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": ["exp", "iss", "aud", "sub", "role", "permissions"]
                },
            )
            role, permissions = claims["role"], claims["permissions"]
            if (
                role not in ("lawyer", "admin")
                or not isinstance(permissions, list)
                or any(
                    not isinstance(p, str) or p not in PERMISSIONS for p in permissions
                )
            ):
                raise ValueError("invalid claims")
            if role == "lawyer" and any(p.startswith("users:") for p in permissions):
                raise ValueError("invalid role permissions")
            return VerifiedActor(
                UUID(claims["sub"]), role, frozenset(permissions), request_id
            )
        except (ValueError, TypeError, KeyError, jwt.PyJWTError) as exc:
            raise ValueError("invalid access token") from exc
