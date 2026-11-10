from typing import Any, Generic, Protocol, TypeVar, cast

TResult = TypeVar("TResult")


class Command(Generic[TResult]):  # noqa: UP046
    """Маркер: команда, которая возвращает TResult."""


class CommandHandler[TCommand, R](Protocol):
    async def handle(self, cmd: TCommand) -> R: ...


class Mediator:
    def __init__(self) -> None:
        self._handlers: dict[type[Any], CommandHandler[Any, Any]] = {}

    def register[R](
        self,
        command_type: type[Command[R]],
        handler: CommandHandler[Any, R],
    ) -> None:
        self._handlers[command_type] = handler

    async def send[R](self, command: Command[R]) -> R:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise LookupError(f"No handler registered for {type(command).__name__}")
        return cast(R, await handler.handle(command))
