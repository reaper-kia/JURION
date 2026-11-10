import grpc
import pytest

from identity_service.applications.exceptions import InvalidCredentialsError, UserNotActiveError
from identity_service.domain.exceptions import UserAlreadyRegisterError, WeakPasswordError
from identity_service.transport.grpc.errors import find_status_code


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (WeakPasswordError("too short"), grpc.StatusCode.INVALID_ARGUMENT),
        (UserAlreadyRegisterError("exists"), grpc.StatusCode.ALREADY_EXISTS),
        (InvalidCredentialsError("bad"), grpc.StatusCode.UNAUTHENTICATED),
        (UserNotActiveError("blocked"), grpc.StatusCode.PERMISSION_DENIED),
        (RuntimeError("database is down"), None),
    ],
)
def test_find_status_code(error: Exception, expected: grpc.StatusCode | None) -> None:
    assert find_status_code(error) == expected
