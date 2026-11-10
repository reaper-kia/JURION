from datetime import datetime, timedelta
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from identity_service.applications.ports.access_token import AccessTokenClaims, IssuedAccessToken


class PyJWTAccessTokenIssuer:
    def __init__(
        self,
        *,
        private_key: str,  # RSA private key, которым Identity подписывает токены.
        issuer: str,
        audience: str,
        ttl: timedelta,
    ) -> None:
        key = serialization.load_pem_private_key(private_key.encode(), password=None)
        if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
            raise ValueError("An RSA private key of at least 2048 bits is required")
        self._private_key = key
        self._issuer = issuer  # кто выыпустил jwt
        self._audience = audience
        self._ttl = ttl  # Сколько живет jwt

    def issue(
        self,
        claims: AccessTokenClaims,
        *,
        now: datetime,
    ) -> IssuedAccessToken:
        expires_at = now + self._ttl

        payload = {
            "sub": str(claims.user_id),
            "sid": str(claims.session_id),
            "fid": str(claims.family_id),
            "jti": str(uuid4()),
            "role": claims.role.value,
            "permissions": sorted(permission.value for permission in claims.permissions),
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": expires_at,
        }

        token = jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
        )

        return IssuedAccessToken(
            value=token,
            expires_at=expires_at,
        )
