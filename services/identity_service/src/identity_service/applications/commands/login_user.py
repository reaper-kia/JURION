from dataclasses import dataclass

from identity_service.applications.mediator import Command
from identity_service.applications.results.authentication import AuthenticationResult


@dataclass(frozen=True)
class LoginUserCommand(Command[AuthenticationResult]):
    email: str
    password: str
