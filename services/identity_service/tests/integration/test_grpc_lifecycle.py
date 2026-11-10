from datetime import timedelta

import grpc
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from identity.v1 import identity_service_pb2 as pb
from identity.v1 import identity_service_pb2_grpc as rpc

from identity_service.applications.commands.create_admin import CreateAdmin
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.dependencies import AuthDeps, build_mediator
from identity_service.infra.access_token import PyJWTAccessTokenIssuer
from identity_service.infra.hashers.password_hasher import Argon2PasswordHasher
from identity_service.infra.hashers.refresh_token import SecureRefreshTokenService
from identity_service.infra.uow.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWorkFactory
from identity_service.transport.grpc.server import create_server


@pytest.mark.asyncio
async def test_grpc_user_lifecycle_and_block(db_session_factory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    issuer = PyJWTAccessTokenIssuer(
        private_key=pem, issuer="jurion-identity", audience="jurion-api", ttl=timedelta(minutes=10)
    )
    deps = AuthDeps(
        SQLAlchemyUnitOfWorkFactory(db_session_factory),
        Argon2PasswordHasher(),
        TokenPairFactory(SecureRefreshTokenService(), issuer, timedelta(days=30)),
    )
    mediator = build_mediator(deps, db_session_factory)
    admin_id = await mediator.send(CreateAdmin("admin@example.com", "Admin", "correct-password"))
    server, port = await create_server(mediator, "127.0.0.1:0", "test-service-token")
    await server.start()
    metadata = (("x-jurion-service-token", "test-service-token"),)
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = rpc.IdentityServiceStub(channel)
            auth = await stub.Register(
                pb.RegisterRequest(
                    email="user@example.com", nickname="User", password="correct-password"
                ),
                metadata=metadata,
            )
            ctx = pb.RequestContext(
                actor_identity_user_id=auth.user.user_id,
                permissions=["conversations:use", "sources:read"],
            )
            assert (
                await stub.GetMe(pb.GetMeRequest(context=ctx), metadata=metadata)
            ).user.user_id == auth.user.user_id
            with pytest.raises(grpc.aio.AioRpcError) as denied:
                await stub.ListUsers(pb.ListUsersRequest(context=ctx, limit=10), metadata=metadata)
            assert denied.value.code() == grpc.StatusCode.PERMISSION_DENIED
            rotated = await stub.RefreshToken(
                pb.RefreshTokenRequest(refresh_token=auth.tokens.refresh_token), metadata=metadata
            )
            admin = pb.RequestContext(
                actor_identity_user_id=str(admin_id), permissions=["users:read", "users:block"]
            )
            assert (
                len(
                    (
                        await stub.ListUsers(
                            pb.ListUsersRequest(context=admin, limit=10), metadata=metadata
                        )
                    ).users
                )
                == 2
            )
            blocked = await stub.BlockUser(
                pb.BlockUserRequest(context=admin, user_id=auth.user.user_id, reason="test"),
                metadata=metadata,
            )
            assert blocked.user.status == pb.USER_STATUS_BLOCKED
            with pytest.raises(grpc.aio.AioRpcError) as rejected:
                await stub.RefreshToken(
                    pb.RefreshTokenRequest(refresh_token=rotated.tokens.refresh_token),
                    metadata=metadata,
                )
            assert rejected.value.code() == grpc.StatusCode.UNAUTHENTICATED
            with pytest.raises(grpc.aio.AioRpcError) as rejected:
                await stub.Login(
                    pb.LoginRequest(email="user@example.com", password="correct-password"),
                    metadata=metadata,
                )
            assert rejected.value.code() == grpc.StatusCode.UNAUTHENTICATED
    finally:
        await server.stop(grace=None)
