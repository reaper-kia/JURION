from dataclasses import dataclass

from identity_service.applications.commands.create_admin import CreateAdmin
from identity_service.domain.entities import User, UserRole
from identity_service.domain.exceptions import UserAlreadyRegisterError
from identity_service.domain.value_objects import Email, Nickname, RawPassword


@dataclass
class CreateAdminHandler:
    uow_factory: object
    password_hasher: object

    async def handle(self, command: CreateAdmin):
        email, nickname, password = (
            Email(command.email),
            Nickname(command.nickname),
            RawPassword(command.password),
        )
        password_hash = await self.password_hasher.hash(password.value)
        async with self.uow_factory() as uow:
            if await uow.users.get_by_email(email):
                raise UserAlreadyRegisterError("Email already exists")
            user = User.register(email, nickname, password_hash)
            user.change_role(UserRole.ADMIN)
            await uow.users.add(user)
            await uow.commit()
            return user.id
