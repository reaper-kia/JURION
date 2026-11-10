from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity_service.domain.entities import RefreshSession, User
from identity_service.domain.value_objects import Email, Nickname
from identity_service.infra.database.models import RefreshSessionModel, UserModel
from identity_service.infra.uow.sqlalchemy_unit_of_work import (
    SQLAlchemyUnitOfWorkFactory,
)


def make_user(suffix: str) -> User:
    return User.register(
        email=Email(f"uow-{suffix}@example.com"),
        nickname=Nickname(f"uow-{suffix}"),
        password_hash="argon2-test-hash",
    )


def make_session(user: User, token_character: str) -> RefreshSession:
    return RefreshSession(
        user_id=user.id,
        token_hash=token_character * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


@pytest.mark.asyncio
async def test_commit_persists_user_and_refresh_session_atomically(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = SQLAlchemyUnitOfWorkFactory(db_session_factory)
    user = make_user("commit")
    refresh_session = make_session(user, "j")

    async with factory() as uow:
        await uow.users.add(user)
        await uow.refresh_sessions.add(refresh_session)
        await uow.commit()

    async with db_session_factory() as database_session:
        user_count = await database_session.scalar(select(func.count()).select_from(UserModel))
        session_count = await database_session.scalar(
            select(func.count()).select_from(RefreshSessionModel)
        )

        assert user_count == 1
        assert session_count == 1


@pytest.mark.asyncio
async def test_exception_rolls_back_user_and_refresh_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = SQLAlchemyUnitOfWorkFactory(db_session_factory)
    user = make_user("rollback")
    refresh_session = make_session(user, "k")

    with pytest.raises(RuntimeError, match="force rollback"):
        async with factory() as uow:
            await uow.users.add(user)
            await uow.refresh_sessions.add(refresh_session)
            await uow.session.flush()
            raise RuntimeError("force rollback")

    async with db_session_factory() as database_session:
        user_count = await database_session.scalar(select(func.count()).select_from(UserModel))
        session_count = await database_session.scalar(
            select(func.count()).select_from(RefreshSessionModel)
        )

        assert user_count == 0
        assert session_count == 0


@pytest.mark.asyncio
async def test_rotation_links_old_session_to_new_one(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = SQLAlchemyUnitOfWorkFactory(db_session_factory)
    user = make_user("rotate")
    old = make_session(user, "m")

    async with factory() as uow:
        await uow.users.add(user)
        await uow.refresh_sessions.add(old)
        await uow.commit()

    new = make_session(user, "n")
    async with factory() as uow:
        await uow.refresh_sessions.add(new)  # INSERT new
        old.replace_with(new.id)
        await uow.refresh_sessions.save(old)  # UPDATE old -> new.id
        await uow.commit()

    async with db_session_factory() as database_session:
        stored_old = await database_session.get(RefreshSessionModel, old.id)
        assert stored_old is not None
        assert stored_old.replaced_by_session_id == new.id
        assert stored_old.revoked_at is not None
