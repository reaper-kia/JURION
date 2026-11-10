from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserReadModel:
    id: UUID
    email: str
    nickname: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
    password_changed_at: datetime | None
