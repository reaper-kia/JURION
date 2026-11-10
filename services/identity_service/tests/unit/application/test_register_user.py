from datetime import timedelta

import pytest
from auth_fakes import (
    FakeAccessTokenIssuer,
    FakePasswordHasher,
    FakeRefreshTokenService,
    FakeUnitOfWorkFactory,
)

from identity_service.applications.commands.register_user import (
    RegisterUserCommand,
)
from identity_service.applications.handlers.register_user import (
    RegisterUserCommandHandler,
)
from identity_service.applications.services.token_pair_factory import (
    TokenPairFactory,
)
from identity_service.domain.entities import UserRole, UserStatus
from identity_service.domain.exceptions import (
    UserAlreadyRegisterError,
)

REFRESH_TTL = timedelta(days=30)


def make_handler(
    *,
    uow_factory: FakeUnitOfWorkFactory | None = None,
    password_hasher: FakePasswordHasher | None = None,
    refresh_tokens: FakeRefreshTokenService | None = None,
    access_tokens: FakeAccessTokenIssuer | None = None,
) -> tuple[
    RegisterUserCommandHandler,
    FakeUnitOfWorkFactory,
    FakePasswordHasher,
    FakeRefreshTokenService,
    FakeAccessTokenIssuer,
]:
    uow_factory = uow_factory or FakeUnitOfWorkFactory()

    password_hasher = password_hasher or FakePasswordHasher()

    refresh_tokens = refresh_tokens or FakeRefreshTokenService(["register-refresh-token"])

    access_tokens = access_tokens or FakeAccessTokenIssuer()

    handler = RegisterUserCommandHandler(
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
async def test_register_creates_user_refresh_session_and_token_pair() -> None:
    (
        handler,
        uow_factory,
        password_hasher,
        refresh_tokens,
        access_tokens,
    ) = make_handler()

    result = await handler.handle(
        RegisterUserCommand(
            email="player@example.com",
            nickname="player_one",
            password="correct-password",
        )
    )

    assert len(uow_factory.state.users) == 1
    assert len(uow_factory.state.refresh_sessions) == 1

    assert uow_factory.last_uow.commit_count == 1
    assert uow_factory.last_uow.rollback_count == 0

    user = uow_factory.state.users[0]
    refresh_session = uow_factory.state.refresh_sessions[0]

    assert user.email.value == "player@example.com"
    assert user.nickname.value == "player_one"

    assert user.role is UserRole.LAWYER
    assert user.status is UserStatus.ACTIVE

    assert user.password_hash == password_hasher.password_hash
    assert user.password_hash != "correct-password"

    expected_refresh_hash = refresh_tokens.hash("register-refresh-token")

    assert refresh_session.user_id == user.id
    assert refresh_session.token_hash == expected_refresh_hash
    assert refresh_session.token_hash != "register-refresh-token"
    assert refresh_session.revoked_at is None

    assert result.user.id == user.id

    assert result.tokens.refresh_token == "register-refresh-token"
    assert result.tokens.access_token.startswith("access-token-")
    assert result.tokens.refresh_token_expire_at > refresh_session.created_at

    assert len(access_tokens.claims) == 1

    claims = access_tokens.claims[0]

    assert claims.user_id == user.id
    assert claims.session_id == refresh_session.id
    assert claims.family_id == refresh_session.family_id
    assert claims.role is UserRole.LAWYER


@pytest.mark.asyncio
async def test_register_normalizes_email_before_lookup_and_persistence() -> None:
    handler, uow_factory, *_ = make_handler()

    await handler.handle(
        RegisterUserCommand(
            email="  Player@Example.COM  ",
            nickname="player_one",
            password="correct-password",
        )
    )

    assert uow_factory.state.users[0].email.value == "player@example.com"


@pytest.mark.asyncio
async def test_duplicate_email_after_normalization_does_not_create_second_user() -> None:
    handler, uow_factory, *_ = make_handler(
        refresh_tokens=FakeRefreshTokenService(
            [
                "first-refresh-token",
                "second-refresh-token",
            ]
        )
    )

    await handler.handle(
        RegisterUserCommand(
            email="Player@Example.com",
            nickname="first_player",
            password="correct-password",
        )
    )

    with pytest.raises(UserAlreadyRegisterError):
        await handler.handle(
            RegisterUserCommand(
                email="  player@example.COM ",
                nickname="second_player",
                password="correct-password",
            )
        )

    assert len(uow_factory.state.users) == 1
    assert len(uow_factory.state.refresh_sessions) == 1

    assert uow_factory.last_uow.commit_count == 0
    assert uow_factory.last_uow.rollback_count == 1


@pytest.mark.asyncio
async def test_register_does_not_store_plaintext_password_or_refresh_token() -> None:
    raw_password = "correct-password"
    raw_refresh_token = "raw-refresh-secret"

    handler, uow_factory, *_ = make_handler(
        refresh_tokens=FakeRefreshTokenService([raw_refresh_token])
    )

    await handler.handle(
        RegisterUserCommand(
            email="player@example.com",
            nickname="player_one",
            password=raw_password,
        )
    )

    persisted_state = repr(
        (
            uow_factory.state.users,
            uow_factory.state.refresh_sessions,
        )
    )

    assert raw_password not in persisted_state
    assert raw_refresh_token not in persisted_state


@pytest.mark.asyncio
async def test_register_hashes_password_before_entering_persistence_state() -> None:
    password_hasher = FakePasswordHasher(password_hash=("$argon2id$opaque-test-hash"))

    (
        handler,
        uow_factory,
        password_hasher,
        *_,
    ) = make_handler(password_hasher=password_hasher)

    await handler.handle(
        RegisterUserCommand(
            email="player@example.com",
            nickname="player_one",
            password="correct-password",
        )
    )

    assert password_hasher.hash_calls == ["correct-password"]

    assert uow_factory.state.users[0].password_hash == "$argon2id$opaque-test-hash"


@pytest.mark.asyncio
async def test_register_uses_single_now_for_both_tokens() -> None:
    handler, *_ = make_handler()

    result = await handler.handle(
        RegisterUserCommand(
            email="player@example.com",
            nickname="player_one",
            password="correct-password",
        )
    )

    # FakeAccessTokenIssuer по умолчанию выдаёт токен на 15 минут
    access_ttl = timedelta(minutes=15)

    assert (
        result.tokens.refresh_token_expire_at - result.tokens.access_token_expire_at
        == REFRESH_TTL - access_ttl
    )
