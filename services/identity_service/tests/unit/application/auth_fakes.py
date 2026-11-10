from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

from identity_service.applications.ports.access_token import (
    AccessTokenClaims,
    IssuedAccessToken,
)
from identity_service.applications.services.token_pair_factory import TokenPairFactory
from identity_service.dependencies import AuthDeps
from identity_service.domain.entities import (
    RefreshSession,
    User,
    UserRole,
    UserStatus,
)
from identity_service.domain.value_objects import Email, Nickname


@dataclass
class FakeState:
    users: list[User] = field(default_factory=list)
    refresh_sessions: list[RefreshSession] = field(default_factory=list)


class FakeUserRepository:
    def __init__(self, state: FakeState, staged: list[User]) -> None:
        self._state = state
        self._staged = staged

    async def add(self, user: User) -> None:
        self._staged.append(user)

    async def save(self, user: User) -> None:
        for index, current in enumerate(self._state.users):
            if current.id == user.id:
                self._state.users[index] = user
                return

        for index, current in enumerate(self._staged):
            if current.id == user.id:
                self._staged[index] = user
                return

        raise AssertionError(f"User {user.id} was not added to fake repository")

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next(
            (user for user in [*self._staged, *self._state.users] if user.id == user_id),
            None,
        )

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        return await self.get_by_id(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        return next(
            (user for user in [*self._staged, *self._state.users] if user.email == email),
            None,
        )


class FakeRefreshSessionRepository:
    def __init__(
        self,
        state: FakeState,
        staged: list[RefreshSession],
    ) -> None:
        self._state = state
        self._staged = staged

    async def add(self, session: RefreshSession) -> None:
        self._staged.append(session)

    async def save(self, session: RefreshSession) -> None:
        for index, current in enumerate(self._state.refresh_sessions):
            if current.id == session.id:
                self._state.refresh_sessions[index] = session
                return

        for index, current in enumerate(self._staged):
            if current.id == session.id:
                self._staged[index] = session
                return

        raise AssertionError(f"Refresh session {session.id} was not added to fake repository")

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        return await self.get_by_token_hash_for_update(token_hash)

    async def get_by_token_hash_for_update(
        self,
        token_hash: str,
    ) -> RefreshSession | None:
        return next(
            (
                session
                for session in [
                    *self._staged,
                    *self._state.refresh_sessions,
                ]
                if session.token_hash == token_hash
            ),
            None,
        )

    async def revoke_family(
        self,
        family_id: UUID,
        revoked_at: datetime,
    ) -> None:
        for session in [
            *self._staged,
            *self._state.refresh_sessions,
        ]:
            if session.family_id == family_id and session.revoked_at is None:
                session.revoked_at = revoked_at

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        revoked_at: datetime,
    ) -> None:
        for session in [
            *self._staged,
            *self._state.refresh_sessions,
        ]:
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = revoked_at


class FakeUnitOfWork:
    def __init__(self, state: FakeState) -> None:
        self._state = state

        self._staged_users: list[User] = []
        self._staged_refresh_sessions: list[RefreshSession] = []

        self.users = FakeUserRepository(
            state,
            self._staged_users,
        )
        self.refresh_sessions = FakeRefreshSessionRepository(
            state,
            self._staged_refresh_sessions,
        )

        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self._state.users.extend(self._staged_users)
        self._state.refresh_sessions.extend(self._staged_refresh_sessions)

        self._staged_users.clear()
        self._staged_refresh_sessions.clear()

        self.commit_count += 1

    async def rollback(self) -> None:
        self._staged_users.clear()
        self._staged_refresh_sessions.clear()

        self.rollback_count += 1


class FakeUnitOfWorkFactory:
    def __init__(
        self,
        state: FakeState | None = None,
    ) -> None:
        self.state = state or FakeState()
        self.created: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        uow = FakeUnitOfWork(self.state)
        self.created.append(uow)
        return uow

    @property
    def last_uow(self) -> FakeUnitOfWork:
        assert self.created, "UnitOfWork was not created"
        return self.created[-1]


class FakePasswordHasher:
    def __init__(
        self,
        *,
        valid_password: str = "correct-password",
        password_hash: str = "$argon2id$fake-hash",
    ) -> None:
        self.valid_password = valid_password
        self.password_hash = password_hash

        self.hash_calls: list[str] = []
        self.verify_calls: list[tuple[object, str]] = []

    async def hash(self, raw_password: str) -> str:
        self.hash_calls.append(raw_password)
        return self.password_hash

    async def verify(
        self,
        raw_password: str,
        password_hash: str,
    ) -> bool:
        self.verify_calls.append((raw_password, password_hash))

        return (
            isinstance(raw_password, str)
            and raw_password == self.valid_password
            and password_hash == self.password_hash
        )


class FakeRefreshTokenService:
    def __init__(
        self,
        tokens: list[str] | None = None,
    ) -> None:
        self._tokens = list(tokens or ["refresh-token-1"])

        self.generate_count = 0
        self.hashed_raw_tokens: list[str] = []

    def generate(self) -> str:
        self.generate_count += 1

        if self._tokens:
            return self._tokens.pop(0)

        return f"refresh-token-{self.generate_count}"

    def hash(self, raw_token: str) -> str:
        self.hashed_raw_tokens.append(raw_token)

        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class FakeAccessTokenIssuer:
    def __init__(
        self,
        ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self.ttl = ttl
        self.claims: list[AccessTokenClaims] = []

    def issue(
        self,
        claims: AccessTokenClaims,
        *,
        now: datetime,
    ) -> IssuedAccessToken:
        self.claims.append(claims)

        return IssuedAccessToken(
            value=f"access-token-{claims.session_id}",
            expires_at=now + self.ttl,
        )


def make_user(
    *,
    email: str = "player@example.com",
    nickname: str = "player_one",
    password_hash: str = "$argon2id$fake-hash",
    role: UserRole = UserRole.LAWYER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    return User(
        email=Email(email),
        nickname=Nickname(nickname),
        password_hash=password_hash,
        role=role,
        status=status,
    )


def make_auth_deps() -> AuthDeps:
    """Настоящие обработчики поверх фейковой инфраструктуры: без БД, ключей и сети."""
    return AuthDeps(
        uow_factory=FakeUnitOfWorkFactory(),
        password_hasher=FakePasswordHasher(),
        token_pair_factory=TokenPairFactory(
            refresh_tokens=FakeRefreshTokenService(),
            access_tokens=FakeAccessTokenIssuer(),
            refresh_token_ttl=timedelta(days=30),
        ),
    )
