from datetime import datetime
from typing import Protocol
from uuid import UUID

from identity_service.applications.pagination import UserCursor
from identity_service.applications.results.read_models import UserReadModel
from identity_service.domain.entities import RefreshSession, User, UserRole, UserStatus
from identity_service.domain.value_objects import Email


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def save(self, user: User) -> None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def get_by_id_for_update(self, user_id: UUID) -> User | None: ...


class UserReadRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> UserReadModel | None: ...

    async def get_by_email(self, email: Email) -> UserReadModel | None: ...

    async def list_users(
        self,
        *,
        limit: int = 50,
        after: UserCursor | None = None,
        status: UserStatus | None = None,
        role: UserRole | None = None,
    ) -> list[UserReadModel]: ...


class RefreshSessionRepository(Protocol):
    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None: ...

    async def add(self, session: RefreshSession) -> None: ...

    async def save(self, session: RefreshSession) -> None: ...

    async def get_by_token_hash_for_update(
        self,
        token_hash: str,
    ) -> RefreshSession | None: ...

    async def revoke_family(
        self,
        family_id: UUID,
        revoked_at: datetime,
    ) -> None: ...

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        revoked_at: datetime,
    ) -> None: ...
