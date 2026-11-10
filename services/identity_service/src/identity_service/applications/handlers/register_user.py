from dataclasses import dataclass

from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.ports.password_hasher import PasswordHasher
from identity_service.applications.ports.unit_of_work import UnitOfWorkFactory
from identity_service.applications.results.authentication import (
    AuthenticationResult,
)
from identity_service.applications.results.read_models import UserReadModel
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.domain.entities import User, utc_now
from identity_service.domain.exceptions import UserAlreadyRegisterError
from identity_service.domain.value_objects import Email, Nickname, RawPassword


@dataclass
class RegisterUserCommandHandler:
    uow_factory: UnitOfWorkFactory
    password_hasher: PasswordHasher
    token_pair_factory: TokenPairFactory

    async def handle(self, cmd: RegisterUserCommand) -> AuthenticationResult:
        email = Email(cmd.email)
        nickname = Nickname(cmd.nickname)
        raw_password = RawPassword(cmd.password)

        password_hash = await self.password_hasher.hash(raw_password.value)

        async with self.uow_factory() as uow:
            if await uow.users.get_by_email(email) is not None:
                raise UserAlreadyRegisterError("User email already register")

            user = User.register(
                email=email,
                nickname=nickname,
                password_hash=password_hash,
            )

            created_tokens = self.token_pair_factory.create(
                user=user,
                now=utc_now(),
            )

            await uow.users.add(user)
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
