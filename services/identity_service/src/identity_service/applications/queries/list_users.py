from dataclasses import dataclass

from identity_service.domain.entities import UserRole, UserStatus


@dataclass(frozen=True)
class ListUsersQuery:
    limit: int
    cursor: str | None
    role: UserRole | None
    status: UserStatus | None
