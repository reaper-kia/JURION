from gateway.application.core import Command


class RegisterCommand(Command):
    pass


class LoginCommand(Command):
    pass


class RefreshSessionCommand(Command):
    pass


class LogoutCommand(Command):
    pass


class CreateConversationCommand(Command):
    pass


class SendMessageCommand(Command):
    pass


class RetryRunCommand(Command):
    pass


COMMANDS = {
    "Register": RegisterCommand,
    "Login": LoginCommand,
    "RefreshToken": RefreshSessionCommand,
    "Logout": LogoutCommand,
    "CreateConversation": CreateConversationCommand,
    "SendMessage": SendMessageCommand,
    "RetryRun": RetryRunCommand,
}
