from types import TracebackType
from typing import Protocol, Self

from identity_service.applications.ports.repositories import (
    RefreshSessionRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    users: UserRepository
    refresh_sessions: RefreshSessionRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
