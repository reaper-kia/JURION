from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from identity_service.domain.value_objects import Email, Nickname


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    LAWYER = "lawyer"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


@dataclass(slots=True, kw_only=True)
class User:
    email: Email
    nickname: Nickname
    password_hash: str

    id: UUID = field(default_factory=uuid4)
    role: UserRole = UserRole.LAWYER
    status: UserStatus = UserStatus.ACTIVE
    password_algorithm: str = "argon2id"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    password_changed_at: datetime = field(default_factory=utc_now)

    @classmethod
    def register(cls, email: Email, nickname: Nickname, password_hash: str) -> "User":
        return cls(
            email=email,
            nickname=nickname,
            password_hash=password_hash,
        )

    def change_role(self, role: UserRole) -> None:
        if self.role == role:
            return
        self.role = role

    def change_email(self, email: Email) -> None:
        if self.email == email:
            return
        self.email = email

    def change_nickname(self, nickname: Nickname) -> None:
        if self.nickname == nickname:
            return
        self.nickname = nickname

    def change_password(self, password_hash: str, algorithm: str) -> None:
        self.password_hash = password_hash
        self.password_algorithm = algorithm
        self.password_changed_at = utc_now()
        self.updated_at = self.password_changed_at

    def block(self) -> None:
        self.status = UserStatus.BLOCKED
        self.updated_at = utc_now()


@dataclass(slots=True, kw_only=True)
class RefreshSession:
    user_id: UUID
    token_hash: str
    expires_at: datetime

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    family_id: UUID = field(default_factory=uuid4)
    replaced_by_session_id: UUID | None = None

    def revoke(self) -> None:
        if self.revoked_at is not None:
            return

        self.revoked_at = utc_now()

    def replace_with(self, replacement_id: UUID) -> None:
        if self.revoked_at is not None:
            return

        self.revoked_at = utc_now()
        self.replaced_by_session_id = replacement_id

    def is_active(self, now: datetime | None = None) -> bool:
        current_time = now or utc_now()

        return self.revoked_at is None and self.expires_at > current_time
