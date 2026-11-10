from dataclasses import dataclass
from uuid import UUID

from identity_service.applications.exceptions import UserNotFoundError
from identity_service.applications.ports.repositories import UserReadRepository
from identity_service.applications.results.read_models import UserReadModel


@dataclass
class GetUserByIdQueryHandler:
    user_read_repository: UserReadRepository

    async def handle(self, user_id: UUID) -> UserReadModel:
        user = await self.user_read_repository.get_by_id(user_id)

        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        return user
