from dataclasses import dataclass

from identity_service.applications.results.read_models import UserReadModel


@dataclass(frozen=True)
class ListUsersResult:
    users: list[UserReadModel]
    next_cursor: str | None
