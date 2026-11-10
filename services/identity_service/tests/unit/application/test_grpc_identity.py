"""Сквозные тесты gRPC-слоя: настоящий сервер на свободном порту, фейковая инфраструктура."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import grpc
import pytest
from auth_fakes import make_auth_deps
from identity.v1 import identity_service_pb2 as pb
from identity.v1 import identity_service_pb2_grpc as pb_grpc

from identity_service.dependencies import build_mediator
from identity_service.transport.grpc.server import create_server


@asynccontextmanager
async def running_stub(mediator: Any) -> AsyncIterator[pb_grpc.IdentityServiceStub]:
    server, port = await create_server(
        mediator, "127.0.0.1:0", "test-service-token"
    )  # 0 = любой свободный порт
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = pb_grpc.IdentityServiceStub(channel)
            for name in (
                "Register",
                "Login",
                "GetMe",
                "RefreshToken",
                "Logout",
                "GetUser",
                "ListUsers",
                "BlockUser",
            ):
                method = getattr(stub, name)

                def authenticated(request, _method=method, **kwargs):
                    return _method(
                        request,
                        metadata=(("x-jurion-service-token", "test-service-token"),),
                        **kwargs,
                    )

                setattr(stub, name, authenticated)
            yield stub
    finally:
        await server.stop(grace=None)


def register_request(**overrides: str) -> pb.RegisterRequest:
    fields = {
        "email": "player@example.com",
        "nickname": "player_one",
        "password": "correct-password",
    }
    fields.update(overrides)
    return pb.RegisterRequest(context=pb.RequestContext(request_id="test-req"), **fields)


async def test_register_returns_user_and_tokens() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        response = await stub.Register(register_request(email="  Player@Example.COM "), timeout=5)

    assert response.user.email == "player@example.com"
    assert response.user.nickname == "player_one"
    assert response.user.role == pb.USER_ROLE_LAWYER
    assert response.user.status == pb.USER_STATUS_ACTIVE
    assert response.user.user_id
    assert response.user.created_at.seconds > 0

    assert response.tokens.access_token
    assert response.tokens.refresh_token
    assert (
        response.tokens.refresh_token_expires_at.seconds
        > response.tokens.access_token_expires_at.seconds
    )


async def test_login_after_register_returns_same_user() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        registered = await stub.Register(register_request(), timeout=5)
        logged_in = await stub.Login(
            pb.LoginRequest(email="player@example.com", password="correct-password"), timeout=5
        )

    assert logged_in.user.user_id == registered.user.user_id
    assert logged_in.tokens.refresh_token != registered.tokens.refresh_token


@pytest.mark.parametrize(
    ("request_fields", "expected_code"),
    [
        ({"password": "short"}, grpc.StatusCode.INVALID_ARGUMENT),
        ({"email": "not-an-email"}, grpc.StatusCode.INVALID_ARGUMENT),
        ({"nickname": ""}, grpc.StatusCode.INVALID_ARGUMENT),
    ],
)
async def test_register_validation_errors(
    request_fields: dict[str, str], expected_code: grpc.StatusCode
) -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.Register(register_request(**request_fields), timeout=5)

    assert error.value.code() == expected_code


async def test_register_duplicate_email_is_already_exists() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        await stub.Register(register_request(), timeout=5)
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.Register(register_request(nickname="someone_else"), timeout=5)

    assert error.value.code() == grpc.StatusCode.ALREADY_EXISTS


async def test_login_wrong_password_is_unauthenticated() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        await stub.Register(register_request(), timeout=5)
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.Login(
                pb.LoginRequest(email="player@example.com", password="wrong-password"), timeout=5
            )

    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_login_unknown_email_is_unauthenticated() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.Login(
                pb.LoginRequest(email="nobody@example.com", password="correct-password"), timeout=5
            )

    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_get_me_requires_actor() -> None:
    async with running_stub(build_mediator(make_auth_deps())) as stub:
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.GetMe(pb.GetMeRequest(), timeout=5)

    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


class ExplodingMediator:
    async def send(self, command: Any) -> Any:
        raise RuntimeError("connection to postgres://identity:hunter2@db failed")


async def test_unexpected_error_is_internal_and_hides_details() -> None:
    async with running_stub(ExplodingMediator()) as stub:
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await stub.Register(register_request(), timeout=5)

    assert error.value.code() == grpc.StatusCode.INTERNAL
    assert "hunter2" not in (error.value.details() or "")


async def test_missing_service_token_is_rejected_before_actor():
    server, port = await create_server(
        build_mediator(make_auth_deps()), "127.0.0.1:0", "test-service-token"
    )
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = pb_grpc.IdentityServiceStub(channel)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.GetMe(
                    pb.GetMeRequest(context=pb.RequestContext(actor_identity_user_id="invalid"))
                )
            assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED
            assert error.value.trailing_metadata()["jurion-error-code"] == "SERVICE_UNAUTHENTICATED"
    finally:
        await server.stop(grace=None)
