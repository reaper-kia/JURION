"""Commands and queries for session lifecycle and user administration."""

import logging
from dataclasses import dataclass
from uuid import UUID

from identity_service.applications.authorization import require_actor, require_permission
from identity_service.applications.context import RequestContext
from identity_service.applications.exceptions import (
    PermissionDeniedError,
    UnauthenticatedError,
    UserNotFoundError,
)
from identity_service.applications.handlers.list_users import ListUsersQueryHandler
from identity_service.applications.queries.list_users import ListUsersQuery
from identity_service.applications.results.read_models import UserReadModel
from identity_service.domain.entities import UserRole, UserStatus, utc_now
from identity_service.domain.permissions import Permission

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Logout:
    context: RequestContext
    refresh_token: str
    all_sessions: bool


@dataclass(frozen=True)
class GetMe:
    context: RequestContext


@dataclass(frozen=True)
class GetUser:
    context: RequestContext
    user_id: UUID


@dataclass(frozen=True)
class ListUsers:
    context: RequestContext
    limit: int
    cursor: str | None
    role: UserRole | None
    status: UserStatus | None


@dataclass(frozen=True)
class BlockUser:
    context: RequestContext
    user_id: UUID
    reason: str


class LogoutHandler:
    def __init__(self, uow_factory, refresh_tokens):
        self.uow_factory, self.refresh_tokens = uow_factory, refresh_tokens

    async def handle(self, cmd):
        async with self.uow_factory() as uow:
            if cmd.all_sessions:
                actor = require_actor(cmd.context)
                if await uow.users.get_by_id_for_update(actor):
                    await uow.refresh_sessions.revoke_all_for_user(actor, utc_now())
                    await uow.commit()
                return
            if not cmd.refresh_token:
                return
            token_hash = self.refresh_tokens.hash(cmd.refresh_token)
            initial = await uow.refresh_sessions.get_by_token_hash(token_hash)
            if initial is None:
                return
            user = await uow.users.get_by_id_for_update(initial.user_id)
            session = await uow.refresh_sessions.get_by_token_hash_for_update(token_hash)
            if user is None or session is None or not session.is_active():
                return
            if cmd.context.actor_identity_user_id and cmd.context.actor_identity_user_id != user.id:
                raise PermissionDeniedError("Forbidden")
            await uow.refresh_sessions.revoke_family(session.family_id, utc_now())
            await uow.commit()


class UserQueries:
    def __init__(self, read_repository_factory):
        self.read_repository_factory = read_repository_factory

    async def handle(self, query):
        if isinstance(query, GetMe):
            user_id = require_actor(query.context)
        else:
            require_permission(query.context, Permission.USERS_READ)
            user_id = query.user_id if isinstance(query, GetUser) else None
        async with self.read_repository_factory() as repo:
            if isinstance(query, ListUsers):
                return await ListUsersQueryHandler(repo).handle(
                    ListUsersQuery(query.limit, query.cursor, query.role, query.status)
                )
            user = await repo.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError("User not found")
            if isinstance(query, GetMe) and user.status != UserStatus.ACTIVE.value:
                raise UnauthenticatedError("Authentication required")
            return user


class BlockUserHandler:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    async def handle(self, cmd):
        require_permission(cmd.context, Permission.USERS_BLOCK)
        if require_actor(cmd.context) == cmd.user_id:
            raise PermissionDeniedError("Cannot block yourself")
        if not cmd.reason.strip() or len(cmd.reason) > 500:
            raise ValueError("Reason must contain 1–500 characters")
        async with self.uow_factory() as uow:
            user = await uow.users.get_by_id_for_update(cmd.user_id)
            if user is None:
                raise UserNotFoundError("User not found")
            if user.status != UserStatus.BLOCKED:
                user.block()
                await uow.users.save(user)
                await uow.refresh_sessions.revoke_all_for_user(user.id, utc_now())
                await uow.commit()
                logger.info(
                    "user_blocked actor=%s user=%s reason=%s",
                    cmd.context.actor_identity_user_id,
                    user.id,
                    cmd.reason,
                )
            return UserReadModel(
                id=user.id,
                email=user.email.value,
                nickname=user.nickname.value,
                role=user.role.value,
                status=user.status.value,
                created_at=user.created_at,
                updated_at=user.updated_at,
                password_changed_at=user.password_changed_at,
            )
