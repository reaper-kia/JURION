import binascii
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from identity_service.applications.exceptions import InvalidCursorError


@dataclass(frozen=True, slots=True)
class UserCursor:
    created_at: datetime
    user_id: UUID


def encode_user_cursor(cursor: UserCursor) -> str:
    value = f"{cursor.created_at.isoformat()}|{cursor.user_id}"
    return urlsafe_b64encode(value.encode()).decode()


def decode_user_cursor(value: str) -> UserCursor:
    try:
        decoded = urlsafe_b64decode(value.encode()).decode()
        created_at, user_id = decoded.split("|", maxsplit=1)

        return UserCursor(
            created_at=datetime.fromisoformat(created_at),
            user_id=UUID(user_id),
        )
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise InvalidCursorError("Invalid user cursor") from exc
