from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from identity_service.applications.ports.access_token import AccessTokenClaims
from identity_service.domain.entities import UserRole
from identity_service.domain.permissions import ROLE_PERMISSIONS
from identity_service.infra.access_token import PyJWTAccessTokenIssuer


@pytest.mark.parametrize(
    "role,permissions",
    [
        (UserRole.LAWYER, {"conversations:use", "sources:read"}),
        (UserRole.ADMIN, {"conversations:use", "sources:read", "users:read", "users:block"}),
    ],
)
def test_signed_claims(role, permissions):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    issuer = PyJWTAccessTokenIssuer(
        private_key=pem, issuer="jurion-identity", audience="jurion-api", ttl=timedelta(minutes=10)
    )
    claims = AccessTokenClaims(
        user_id=uuid4(),
        session_id=uuid4(),
        family_id=uuid4(),
        role=role,
        permissions=ROLE_PERMISSIONS[role],
    )
    encoded = issuer.issue(claims, now=datetime.now(UTC)).value
    decoded = jwt.decode(
        encoded,
        key.public_key(),
        algorithms=["RS256"],
        issuer="jurion-identity",
        audience="jurion-api",
    )
    assert decoded["sub"] == str(claims.user_id)
    assert decoded["sid"] == str(claims.session_id)
    assert decoded["fid"] == str(claims.family_id)
    assert decoded["role"] == role.value
    assert set(decoded["permissions"]) == permissions
    assert {"iat", "exp", "jti"} <= decoded.keys()
