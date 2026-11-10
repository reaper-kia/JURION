from dataclasses import dataclass

from identity_service.applications.commands.login_user import LoginUserCommand
from identity_service.applications.exceptions import InvalidCredentialsError
from identity_service.applications.ports.password_hasher import PasswordHasher
from identity_service.applications.ports.unit_of_work import UnitOfWorkFactory
from identity_service.applications.results.authentication import (
    AuthenticationResult,
)
from identity_service.applications.results.read_models import UserReadModel
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.domain.entities import UserStatus, utc_now
from identity_service.domain.exceptions import WeakPasswordError
from identity_service.domain.value_objects import Email, RawPassword


@dataclass
class LoginUserCommandHandler:
    uow_factory: UnitOfWorkFactory
    password_hasher: PasswordHasher
    token_pair_factory: TokenPairFactory

    async def handle(self, cmd: LoginUserCommand) -> AuthenticationResult:
        email = Email(cmd.email)
        try:
            raw_password = RawPassword(cmd.password)
        except WeakPasswordError as exc:
            raise InvalidCredentialsError("Invalid email or password") from exc

        async with self.uow_factory() as uow:
            user = await uow.users.get_by_email(email)

            if user is None:
                raise InvalidCredentialsError("Invalid email or password")

            password_is_valid = await self.password_hasher.verify(
                raw_password=raw_password.value, password_hash=user.password_hash
            )

            if not password_is_valid:
                raise InvalidCredentialsError("Invalid email or password")

            if user.status is not UserStatus.ACTIVE:
                raise InvalidCredentialsError("Invalid email or password")

            verified_password_version = user.password_changed_at
            user = await uow.users.get_by_id_for_update(user.id)
            if (
                user is None
                or user.status is not UserStatus.ACTIVE
                or user.password_changed_at != verified_password_version
            ):
                raise InvalidCredentialsError("Invalid email or password")

            created_tokens = self.token_pair_factory.create(
                user=user,
                now=utc_now(),
            )

            await uow.refresh_sessions.add(created_tokens.refresh_session)
            await uow.commit()

        user_read_model = UserReadModel(
            id=user.id,
            email=user.email.value,
            nickname=user.nickname.value,
            role=user.role.value,
            status=user.status.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
            password_changed_at=user.password_changed_at,
        )

        return AuthenticationResult(
            user=user_read_model,
            tokens=created_tokens.tokens,
        )
