from uuid import UUID

from identity_service.applications.context import RequestContext
from identity_service.applications.exceptions import (
    PermissionDeniedError,
    UnauthenticatedError,
)
from identity_service.domain.permissions import Permission


def require_actor(context: RequestContext) -> UUID:
    actor_id = context.actor_identity_user_id

    if actor_id is None:
        raise UnauthenticatedError("Authentication required")

    return actor_id


def require_permission(
    context: RequestContext,
    permission: Permission,
) -> None:
    require_actor(context)

    if permission.value not in context.permissions:
        raise PermissionDeniedError(f"Permission required: {permission.value}")
