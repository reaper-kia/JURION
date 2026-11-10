from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity_service.applications.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from identity_service.infra.repositories.refresh_session_repository import (
    SQLAlchemyRefreshSessionRepository,
)
from identity_service.infra.repositories.repositories import SQLAlchemyUserRepository


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()

        self.users = SQLAlchemyUserRepository(self.session)
        self.refresh_sessions = SQLAlchemyRefreshSessionRepository(self.session)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class SQLAlchemyUnitOfWorkFactory(UnitOfWorkFactory):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._session_factory = session_factory

    def __call__(self) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(self._session_factory)
