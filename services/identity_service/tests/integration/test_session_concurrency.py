import asyncio
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from identity_service.applications.commands.refresh_token import RefreshTokenCommand
from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.exceptions import RefreshTokenInvalidError
from identity_service.applications.handlers.refresh_token import RefreshTokenCommandHandler
from identity_service.applications.handlers.register_user import RegisterUserCommandHandler
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.infra.access_token import PyJWTAccessTokenIssuer
from identity_service.infra.hashers.password_hasher import Argon2PasswordHasher
from identity_service.infra.hashers.refresh_token import SecureRefreshTokenService
from identity_service.infra.uow.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWorkFactory


@pytest.mark.asyncio
async def test_only_one_concurrent_rotation_succeeds(db_session_factory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    issuer = PyJWTAccessTokenIssuer(
        private_key=pem, issuer="jurion-identity", audience="jurion-api", ttl=timedelta(minutes=10)
    )
    refresh = SecureRefreshTokenService()
    tokens = TokenPairFactory(refresh, issuer, timedelta(days=30))
    factory = SQLAlchemyUnitOfWorkFactory(db_session_factory)
    registered = await RegisterUserCommandHandler(factory, Argon2PasswordHasher(), tokens).handle(
        RegisterUserCommand("User", "user@example.com", "correct-password")
    )
    handler = RefreshTokenCommandHandler(factory, tokens, refresh)
    result = await asyncio.gather(
        handler.handle(RefreshTokenCommand(registered.tokens.refresh_token)),
        handler.handle(RefreshTokenCommand(registered.tokens.refresh_token)),
        return_exceptions=True,
    )
    assert sum(isinstance(value, RefreshTokenInvalidError) for value in result) == 1
    assert sum(not isinstance(value, BaseException) for value in result) == 1
