from dataclasses import dataclass


@dataclass(frozen=True)
class CreateAdmin:
    email: str
    nickname: str
    password: str
