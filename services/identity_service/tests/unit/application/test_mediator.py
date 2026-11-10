import pytest
from auth_fakes import make_auth_deps

from identity_service.applications.commands.login_user import LoginUserCommand
from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.mediator import Mediator
from identity_service.dependencies import build_mediator


async def test_register_then_login_through_mediator() -> None:
    mediator = build_mediator(make_auth_deps())

    registered = await mediator.send(
        RegisterUserCommand(
            nickname="player_one", email="p@example.com", password="correct-password"
        )
    )
    logged_in = await mediator.send(
        LoginUserCommand(email="p@example.com", password="correct-password")
    )

    assert logged_in.user.id == registered.user.id
    assert logged_in.tokens.refresh_token != registered.tokens.refresh_token


async def test_unregistered_command_raises_lookup_error() -> None:
    with pytest.raises(LookupError):
        await Mediator().send(LoginUserCommand(email="p@example.com", password="correct-password"))
