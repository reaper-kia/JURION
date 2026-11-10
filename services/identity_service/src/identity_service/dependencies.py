from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from identity_service.applications.commands.create_admin import CreateAdmin
from identity_service.applications.commands.login_user import LoginUserCommand
from identity_service.applications.commands.refresh_token import RefreshTokenCommand
from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.handlers.create_admin import CreateAdminHandler
from identity_service.applications.handlers.login_user import LoginUserCommandHandler
from identity_service.applications.handlers.refresh_token import RefreshTokenCommandHandler
from identity_service.applications.handlers.register_user import RegisterUserCommandHandler
from identity_service.applications.handlers.session_and_users import (
    BlockUser,
    BlockUserHandler,
    GetMe,
    GetUser,
    ListUsers,
    Logout,
    LogoutHandler,
    UserQueries,
)
from identity_service.applications.mediator import Mediator
from identity_service.applications.ports.password_hasher import PasswordHasher
from identity_service.applications.ports.unit_of_work import UnitOfWorkFactory
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.infra.access_token import PyJWTAccessTokenIssuer
from identity_service.infra.config import Settings
from identity_service.infra.database.database import create_engine, create_session_factory
from identity_service.infra.hashers.password_hasher import Argon2PasswordHasher
from identity_service.infra.hashers.refresh_token import SecureRefreshTokenService
from identity_service.infra.repositories.repositories import SQLAlchemyUserReadRepository
from identity_service.infra.uow.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWorkFactory


@dataclass(frozen=True)
class Container:
    engine: AsyncEngine
    mediator: Mediator

    async def close(self) -> None:
        await self.engine.dispose()


@dataclass(frozen=True)
class AuthDeps:
    """Общие зависимости обработчиков: собираются один раз из настроек."""

    uow_factory: UnitOfWorkFactory
    password_hasher: PasswordHasher
    token_pair_factory: TokenPairFactory


def build_container(settings: Settings) -> Container:
    engine = create_engine(settings)
    deps = build_auth_deps(settings, engine)
    return Container(engine=engine, mediator=build_mediator(deps, create_session_factory(engine)))


def build_auth_deps(settings: Settings, engine: AsyncEngine) -> AuthDeps:
    access_tokens = PyJWTAccessTokenIssuer(
        private_key=settings.access_token_private_key_path.read_text(encoding="utf-8"),
        issuer=settings.access_token_issuer,
        audience=settings.access_token_audience,
        ttl=timedelta(seconds=settings.access_token_ttl_seconds),
    )
    return AuthDeps(
        uow_factory=SQLAlchemyUnitOfWorkFactory(create_session_factory(engine)),
        password_hasher=Argon2PasswordHasher(),
        token_pair_factory=TokenPairFactory(
            refresh_tokens=SecureRefreshTokenService(),
            access_tokens=access_tokens,
            refresh_token_ttl=timedelta(seconds=settings.refresh_token_ttl_seconds),
        ),
    )


def build_mediator(deps: AuthDeps, session_factory=None) -> Mediator:
    """Единственное место, где сценарии привязываются к командам."""
    mediator = Mediator()
    mediator.register(
        RegisterUserCommand,
        RegisterUserCommandHandler(
            uow_factory=deps.uow_factory,
            password_hasher=deps.password_hasher,
            token_pair_factory=deps.token_pair_factory,
        ),
    )
    mediator.register(
        LoginUserCommand,
        LoginUserCommandHandler(
            uow_factory=deps.uow_factory,
            password_hasher=deps.password_hasher,
            token_pair_factory=deps.token_pair_factory,
        ),
    )
    mediator.register(CreateAdmin, CreateAdminHandler(deps.uow_factory, deps.password_hasher))
    refresh = deps.token_pair_factory.refresh_tokens
    mediator.register(
        RefreshTokenCommand,
        RefreshTokenCommandHandler(deps.uow_factory, deps.token_pair_factory, refresh),
    )
    mediator.register(Logout, LogoutHandler(deps.uow_factory, refresh))
    mediator.register(BlockUser, BlockUserHandler(deps.uow_factory))

    @asynccontextmanager
    async def read_repository():
        async with session_factory() as session:
            yield SQLAlchemyUserReadRepository(session)

    queries = UserQueries(read_repository)
    for query in (GetMe, GetUser, ListUsers):
        mediator.register(query, queries)
    return mediator
