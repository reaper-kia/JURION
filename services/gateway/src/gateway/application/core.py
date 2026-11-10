from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class VerifiedActor:
    user_id: UUID
    role: str
    permissions: frozenset[str]
    request_id: str


@dataclass(frozen=True)
class Command:
    service: str
    method: str
    request_id: str
    actor: VerifiedActor | None
    data: dict[str, Any]


@dataclass(frozen=True)
class Query(Command):
    pass


class ServicePort(Protocol):
    async def call(self, operation: Command) -> Any: ...


class Dispatcher:
    def __init__(self, ports: dict[str, ServicePort]):
        self.ports = ports

    async def dispatch(self, operation: Command) -> Any:
        return await self.ports[operation.service].call(operation)
