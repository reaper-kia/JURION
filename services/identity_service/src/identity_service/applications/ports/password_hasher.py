from typing import Protocol


class PasswordHasher(Protocol):
    async def hash(self, raw_password: str) -> str: ...

    async def verify(self, raw_password: str, password_hash: str) -> bool: ...
