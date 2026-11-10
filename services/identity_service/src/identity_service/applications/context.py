from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    actor_identity_user_id: UUID | None
    permissions: frozenset[str]
