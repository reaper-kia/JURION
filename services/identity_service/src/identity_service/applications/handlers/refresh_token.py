from dataclasses import dataclass

from identity_service.applications.commands.refresh_token import RefreshTokenCommand
from identity_service.applications.exceptions import (
    RefreshTokenInvalidError,
)
from identity_service.applications.ports.refresh_token import RefreshTokenService
from identity_service.applications.ports.unit_of_work import UnitOfWorkFactory
from identity_service.applications.results.authentication import TokenPairResult
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.domain.entities import UserStatus, utc_now


@dataclass
class RefreshTokenCommandHandler:
    uow_factory: UnitOfWorkFactory
    token_pair_factory: TokenPairFactory
    refresh_tokens: RefreshTokenService

    async def handle(self, cmd: RefreshTokenCommand) -> TokenPairResult:
        token_hash = self.refresh_tokens.hash(cmd.refresh_token)
        now = utc_now()

        async with self.uow_factory() as uow:
            preliminary = await uow.refresh_sessions.get_by_token_hash(token_hash)
            if preliminary is None:
                raise RefreshTokenInvalidError("Invalid refresh token")
            user = await uow.users.get_by_id_for_update(preliminary.user_id)
            current_session = await uow.refresh_sessions.get_by_token_hash_for_update(token_hash)
            now = utc_now()
            if user is None or current_session is None or not current_session.is_active(now):
                raise RefreshTokenInvalidError("Invalid refresh token")
            if user.status is not UserStatus.ACTIVE:
                raise RefreshTokenInvalidError("Invalid refresh token")

            created_tokens = self.token_pair_factory.create(
                user=user,
                now=now,
                family_id=current_session.family_id,
            )

            await uow.refresh_sessions.add(created_tokens.refresh_session)

            current_session.replace_with(created_tokens.refresh_session.id)

            await uow.refresh_sessions.save(current_session)

            await uow.commit()

        return created_tokens.tokens
