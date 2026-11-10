from enum import StrEnum
from types import MappingProxyType

from identity_service.domain.entities import UserRole


class Permission(StrEnum):
    CONVERSATIONS_USE = "conversations:use"
    SOURCES_READ = "sources:read"
    USERS_READ = "users:read"
    USERS_BLOCK = "users:block"


ROLE_PERMISSIONS = MappingProxyType(
    {
        UserRole.LAWYER: frozenset({Permission.CONVERSATIONS_USE, Permission.SOURCES_READ}),
        UserRole.ADMIN: frozenset(
            {
                Permission.CONVERSATIONS_USE,
                Permission.SOURCES_READ,
                Permission.USERS_READ,
                Permission.USERS_BLOCK,
            }
        ),
    }
)
