import re
from dataclasses import dataclass

from identity_service.domain.exceptions import (
    InvalidEmailError,
    InvalidNicknameError,
    WeakPasswordError,
)


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)

        if not normalized:
            raise InvalidEmailError("Email can't be empty")

        if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise InvalidEmailError("Invalid email format")


@dataclass(frozen=True)
class Nickname:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidNicknameError("Nickname cann't be empty")

        if len(self.value) > 255:
            raise InvalidNicknameError("Nickname is too long")


@dataclass(frozen=True)
class RawPassword:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) < 8:
            raise WeakPasswordError("Password must contain at least 8 characters")

        if len(self.value) > 128:
            raise WeakPasswordError("Password is too long")
