from dataclasses import dataclass

from identity_service.applications.exceptions import InvalidPageSizeError
from identity_service.applications.pagination import (
    UserCursor,
    decode_user_cursor,
    encode_user_cursor,
)
from identity_service.applications.ports.repositories import UserReadRepository
from identity_service.applications.queries.list_users import ListUsersQuery
from identity_service.applications.results.list_users import ListUsersResult


@dataclass
class ListUsersQueryHandler:
    users_read_repo: UserReadRepository

    async def handle(self, query: ListUsersQuery) -> ListUsersResult:
        if not 1 <= query.limit <= 100:
            raise InvalidPageSizeError("Limit must be between 1 and 100")

        after = decode_user_cursor(query.cursor) if query.cursor is not None else None

        rows = await self.users_read_repo.list_users(
            limit=query.limit + 1,
            after=after,
            status=query.status,
            role=query.role,
        )

        has_more = len(rows) > query.limit
        page = rows[: query.limit]

        next_cursor: str | None = None

        if has_more:
            last_user = page[-1]
            next_cursor = encode_user_cursor(
                UserCursor(
                    created_at=last_user.created_at,
                    user_id=last_user.id,
                )
            )

        return ListUsersResult(
            users=page,
            next_cursor=next_cursor,
        )
