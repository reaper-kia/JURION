import pytest
from auth_fakes import make_auth_deps

from identity_service.applications.commands.refresh_token import RefreshTokenCommand
from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.context import RequestContext
from identity_service.applications.exceptions import (
    PermissionDeniedError,
    RefreshTokenInvalidError,
    UnauthenticatedError,
)
from identity_service.applications.handlers.session_and_users import Logout
from identity_service.dependencies import build_mediator


async def test_rotate_logout_and_reuse():
    mediator = build_mediator(make_auth_deps())
    auth = await mediator.send(RegisterUserCommand("User", "user@example.com", "correct-password"))
    rotated = await mediator.send(RefreshTokenCommand(auth.tokens.refresh_token))
    with pytest.raises(RefreshTokenInvalidError):
        await mediator.send(RefreshTokenCommand(auth.tokens.refresh_token))
    await mediator.send(
        Logout(RequestContext("test", auth.user.id, frozenset()), rotated.refresh_token, False)
    )
    with pytest.raises(RefreshTokenInvalidError):
        await mediator.send(RefreshTokenCommand(rotated.refresh_token))


async def test_logout_requires_actor_for_all_and_rejects_foreign():
    mediator = build_mediator(make_auth_deps())
    a = await mediator.send(RegisterUserCommand("A", "a@example.com", "correct-password"))
    b = await mediator.send(RegisterUserCommand("B", "b@example.com", "correct-password"))
    with pytest.raises(UnauthenticatedError):
        await mediator.send(Logout(RequestContext("test", None, frozenset()), "", True))
    with pytest.raises(PermissionDeniedError):
        await mediator.send(
            Logout(RequestContext("test", b.user.id, frozenset()), a.tokens.refresh_token, False)
        )
    await mediator.send(Logout(RequestContext("test", a.user.id, frozenset()), "", True))
    with pytest.raises(RefreshTokenInvalidError):
        await mediator.send(RefreshTokenCommand(a.tokens.refresh_token))


async def test_expired_refresh_is_rejected():
    from datetime import timedelta

    from identity_service.domain.entities import utc_now

    deps = make_auth_deps()
    mediator = build_mediator(deps)
    auth = await mediator.send(RegisterUserCommand("User", "user@example.com", "correct-password"))
    deps.uow_factory.state.refresh_sessions[0].expires_at = utc_now() - timedelta(seconds=1)
    with pytest.raises(RefreshTokenInvalidError):
        await mediator.send(RefreshTokenCommand(auth.tokens.refresh_token))
