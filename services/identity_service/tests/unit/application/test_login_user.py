from datetime import timedelta

import pytest
from auth_fakes import (
    FakeAccessTokenIssuer,
    FakePasswordHasher,
    FakeRefreshTokenService,
    FakeState,
    FakeUnitOfWorkFactory,
    make_user,
)

from identity_service.applications.commands.login_user import (
    LoginUserCommand,
)
from identity_service.applications.exceptions import (
    InvalidCredentialsError,
)
from identity_service.applications.handlers.login_user import (
    LoginUserCommandHandler,
)
from identity_service.applications.services.token_pair_factory import (
    TokenPairFactory,
)
from identity_service.domain.entities import UserStatus

REFRESH_TTL = timedelta(days=30)


def make_handler(
    *,
    status: UserStatus = UserStatus.ACTIVE,
    valid_password: str = "correct-password",
) -> tuple[
    LoginUserCommandHandler,
    FakeUnitOfWorkFactory,
    FakePasswordHasher,
    FakeRefreshTokenService,
    FakeAccessTokenIssuer,
]:
    password_hasher = FakePasswordHasher(valid_password=valid_password)

    user = make_user(
        email="player@example.com",
        password_hash=(password_hasher.password_hash),
        status=status,
    )

    uow_factory = FakeUnitOfWorkFactory(FakeState(users=[user]))

    refresh_tokens = FakeRefreshTokenService(["login-refresh-token"])

    access_tokens = FakeAccessTokenIssuer()

    handler = LoginUserCommandHandler(
        uow_factory=uow_factory,
        password_hasher=password_hasher,
        token_pair_factory=TokenPairFactory(
            refresh_tokens=refresh_tokens,
            access_tokens=access_tokens,
            refresh_token_ttl=REFRESH_TTL,
        ),
    )

    return (
        handler,
        uow_factory,
        password_hasher,
        refresh_tokens,
        access_tokens,
    )


@pytest.mark.asyncio
async def test_login_with_correct_password_creates_new_refresh_session() -> None:
    (
        handler,
        uow_factory,
        password_hasher,
        refresh_tokens,
        access_tokens,
    ) = make_handler()

    result = await handler.handle(
        LoginUserCommand(
            email="player@example.com",
            password="correct-password",
        )
    )

    assert password_hasher.verify_calls == [
        (
            "correct-password",
            password_hasher.password_hash,
        )
    ]

    assert len(uow_factory.state.refresh_sessions) == 1

    assert uow_factory.last_uow.commit_count == 1
    assert uow_factory.last_uow.rollback_count == 0

    refresh_session = uow_factory.state.refresh_sessions[0]
    user = uow_factory.state.users[0]

    assert refresh_session.user_id == user.id

    expected_refresh_hash = refresh_tokens.hash("login-refresh-token")

    assert refresh_session.token_hash == expected_refresh_hash

    assert result.user.id == user.id

    assert result.tokens.refresh_token == "login-refresh-token"

    assert len(access_tokens.claims) == 1
    assert access_tokens.claims[0].session_id == refresh_session.id


@pytest.mark.asyncio
async def test_login_with_wrong_password_raises_invalid_credentials() -> None:
    handler, uow_factory, *_ = make_handler()

    with pytest.raises(InvalidCredentialsError):
        await handler.handle(
            LoginUserCommand(
                email="player@example.com",
                password="definitely-wrong",
            )
        )

    assert len(uow_factory.state.refresh_sessions) == 0

    assert uow_factory.last_uow.commit_count == 0
    assert uow_factory.last_uow.rollback_count == 1


@pytest.mark.asyncio
async def test_login_unknown_email_returns_same_credentials_error() -> None:
    password_hasher = FakePasswordHasher()
    uow_factory = FakeUnitOfWorkFactory()

    handler = LoginUserCommandHandler(
        uow_factory=uow_factory,
        password_hasher=password_hasher,
        token_pair_factory=TokenPairFactory(
            refresh_tokens=(FakeRefreshTokenService(["unused"])),
            access_tokens=(FakeAccessTokenIssuer()),
            refresh_token_ttl=REFRESH_TTL,
        ),
    )

    with pytest.raises(InvalidCredentialsError):
        await handler.handle(
            LoginUserCommand(
                email="missing@example.com",
                password="correct-password",
            )
        )

    assert password_hasher.verify_calls == []

    assert uow_factory.last_uow.commit_count == 0
    assert uow_factory.last_uow.rollback_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        UserStatus.BLOCKED,
        UserStatus.DELETED,
    ],
)
async def test_login_inactive_user_is_rejected_without_creating_session(
    status: UserStatus,
) -> None:
    handler, uow_factory, *_ = make_handler(status=status)

    with pytest.raises(InvalidCredentialsError):
        await handler.handle(
            LoginUserCommand(
                email="player@example.com",
                password="correct-password",
            )
        )

    assert len(uow_factory.state.refresh_sessions) == 0

    assert uow_factory.last_uow.commit_count == 0
    assert uow_factory.last_uow.rollback_count == 1


@pytest.mark.asyncio
async def test_login_normalizes_email_before_lookup() -> None:
    handler, uow_factory, *_ = make_handler()

    result = await handler.handle(
        LoginUserCommand(
            email="  PLAYER@Example.COM ",
            password="correct-password",
        )
    )

    assert result.user.id == uow_factory.state.users[0].id


@pytest.mark.asyncio
async def test_each_login_starts_new_session_family() -> None:
    handler, uow_factory, *_ = make_handler()

    command = LoginUserCommand(
        email="player@example.com",
        password="correct-password",
    )

    await handler.handle(command)
    await handler.handle(command)

    first, second = uow_factory.state.refresh_sessions

    # Каждый вход — отдельное устройство со своей цепочкой ротации
    assert first.family_id != second.family_id
    assert first.token_hash != second.token_hash

    # Вход с нового устройства не разлогинивает старое
    assert first.revoked_at is None
    assert second.revoked_at is None
