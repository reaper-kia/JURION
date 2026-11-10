from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity_service.domain.entities import RefreshSession, User
from identity_service.domain.value_objects import Email, Nickname
from identity_service.infra.database.models import RefreshSessionModel
from identity_service.infra.repositories.refresh_session_repository import (
    SQLAlchemyRefreshSessionRepository,
)
from identity_service.infra.repositories.repositories import SQLAlchemyUserRepository


def make_user(suffix: str) -> User:
    return User.register(
        email=Email(f"user-{suffix}@example.com"),
        nickname=Nickname(f"user-{suffix}"),
        password_hash="argon2-test-hash",
    )


def make_refresh_session(
    *,
    user_id: UUID,
    token_character: str,
    family_id: UUID | None = None,
) -> RefreshSession:
    expires_at = datetime.now(UTC) + timedelta(days=30)

    if family_id is None:
        return RefreshSession(
            user_id=user_id,
            token_hash=token_character * 64,
            expires_at=expires_at,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    return RefreshSession(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_character * 64,
        expires_at=expires_at,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


@pytest.mark.asyncio
async def test_add_and_get_by_token_hash(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = make_user("add")
    refresh_session = make_refresh_session(
        user_id=user.id,
        token_character="a",
    )

    async with db_session_factory() as database_session:
        await SQLAlchemyUserRepository(database_session).add(user)
        await database_session.flush()
        await SQLAlchemyRefreshSessionRepository(database_session).add(refresh_session)
        await database_session.commit()

    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        loaded = await repository.get_by_token_hash_for_update(refresh_session.token_hash)

        assert loaded is not None
        assert loaded.id == refresh_session.id
        assert loaded.user_id == user.id
        assert loaded.family_id == refresh_session.family_id
        assert loaded.ip_address == "127.0.0.1"
        assert loaded.user_agent == "pytest"


@pytest.mark.asyncio
async def test_get_unknown_token_hash_returns_none(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)

        assert await repository.get_by_token_hash_for_update("x" * 64) is None


@pytest.mark.asyncio
async def test_save_persists_rotation_link(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = make_user("rotation")
    old_session = make_refresh_session(user_id=user.id, token_character="b")

    async with db_session_factory() as database_session:
        await SQLAlchemyUserRepository(database_session).add(user)
        await database_session.flush()
        await SQLAlchemyRefreshSessionRepository(database_session).add(old_session)
        await database_session.commit()

    replacement = make_refresh_session(
        user_id=user.id,
        token_character="c",
        family_id=old_session.family_id,
    )

    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        loaded = await repository.get_by_token_hash_for_update(old_session.token_hash)
        assert loaded is not None

        await repository.add(replacement)
        loaded.replace_with(replacement.id)
        await repository.save(loaded)
        await database_session.commit()

    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        loaded = await repository.get_by_token_hash_for_update(old_session.token_hash)

        assert loaded is not None
        assert loaded.revoked_at is not None
        assert loaded.replaced_by_session_id == replacement.id


@pytest.mark.asyncio
async def test_revoke_family_only_revokes_selected_family(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = make_user("family")
    family_id = uuid4()
    first = make_refresh_session(
        user_id=user.id,
        token_character="d",
        family_id=family_id,
    )
    second = make_refresh_session(
        user_id=user.id,
        token_character="e",
        family_id=family_id,
    )
    unrelated = make_refresh_session(user_id=user.id, token_character="f")

    async with db_session_factory() as database_session:
        await SQLAlchemyUserRepository(database_session).add(user)
        await database_session.flush()
        repository = SQLAlchemyRefreshSessionRepository(database_session)

        for session in (first, second, unrelated):
            await repository.add(session)

        await database_session.commit()

    revoked_at = datetime.now(UTC)

    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        await repository.revoke_family(family_id, revoked_at)
        await database_session.commit()

    async with db_session_factory() as database_session:
        models = (await database_session.execute(select(RefreshSessionModel))).scalars().all()
        by_id = {model.id: model for model in models}

        assert by_id[first.id].revoked_at == revoked_at
        assert by_id[second.id].revoked_at == revoked_at
        assert by_id[unrelated.id].revoked_at is None


@pytest.mark.asyncio
async def test_revoke_all_for_user_does_not_revoke_another_users_sessions(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_user = make_user("first")
    second_user = make_user("second")
    first_session = make_refresh_session(
        user_id=first_user.id,
        token_character="g",
    )
    second_session = make_refresh_session(
        user_id=second_user.id,
        token_character="h",
    )

    async with db_session_factory() as database_session:
        users = SQLAlchemyUserRepository(database_session)
        await users.add(first_user)
        await users.add(second_user)
        await database_session.flush()

        sessions = SQLAlchemyRefreshSessionRepository(database_session)
        await sessions.add(first_session)
        await sessions.add(second_session)
        await database_session.commit()

    revoked_at = datetime.now(UTC)

    async with db_session_factory() as database_session:
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        await repository.revoke_all_for_user(first_user.id, revoked_at)
        await database_session.commit()

    async with db_session_factory() as database_session:
        models = (await database_session.execute(select(RefreshSessionModel))).scalars().all()
        by_id = {model.id: model for model in models}

        assert by_id[first_session.id].revoked_at == revoked_at
        assert by_id[second_session.id].revoked_at is None


@pytest.mark.asyncio
async def test_token_hash_is_unique(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = make_user("unique")
    first = make_refresh_session(user_id=user.id, token_character="i")
    duplicate = make_refresh_session(user_id=user.id, token_character="i")

    async with db_session_factory() as database_session:
        await SQLAlchemyUserRepository(database_session).add(user)
        repository = SQLAlchemyRefreshSessionRepository(database_session)
        await repository.add(first)

        with pytest.raises(IntegrityError):
            await repository.add(duplicate)

        await database_session.rollback()
