from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from identity_service.domain.entities import UserRole
from identity_service.domain.permissions import Permission


@dataclass(frozen=True)
class AccessTokenClaims:  # DTO с данными, которые нужно записать внутрь JWT
    user_id: UUID
    session_id: UUID
    family_id: UUID
    role: UserRole
    permissions: frozenset[Permission]


@dataclass(frozen=True)
class IssuedAccessToken:  # здесь хранится готорая JWT строка и время ее окончания
    value: str
    expires_at: datetime


class AccessTokenIssuer(Protocol):
    def issue(
        self,
        claims: AccessTokenClaims,
        *,
        now: datetime,
    ) -> IssuedAccessToken: ...
