import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

import grpc

from identity_service.applications.exceptions import (
    InvalidCredentialsError,
    InvalidCursorError,
    InvalidPageSizeError,
    PermissionDeniedError,
    RefreshTokenExpiredError,
    RefreshTokenInvalidError,
    UnauthenticatedError,
    UserNotActiveError,
    UserNotFoundError,
)
from identity_service.domain.exceptions import (
    InvalidEmailError,
    InvalidNicknameError,
    UserAlreadyRegisterError,
    WeakPasswordError,
)

logger = logging.getLogger(__name__)

type Context = grpc.aio.ServicerContext[Any, Any]

ERROR_METADATA = {
    InvalidEmailError: "VALIDATION_ERROR",
    InvalidNicknameError: "VALIDATION_ERROR",
    WeakPasswordError: "VALIDATION_ERROR",
    ValueError: "VALIDATION_ERROR",
    InvalidCursorError: "VALIDATION_ERROR",
    InvalidPageSizeError: "VALIDATION_ERROR",
    UserAlreadyRegisterError: "EMAIL_ALREADY_EXISTS",
    InvalidCredentialsError: "INVALID_CREDENTIALS",
    UnauthenticatedError: "AUTH_REQUIRED",
    RefreshTokenInvalidError: "REFRESH_INVALID",
    RefreshTokenExpiredError: "REFRESH_INVALID",
    PermissionDeniedError: "FORBIDDEN",
    UserNotActiveError: "FORBIDDEN",
    UserNotFoundError: "USER_NOT_FOUND",
}

ERROR_CODES: list[tuple[type[Exception], grpc.StatusCode]] = [
    (ValueError, grpc.StatusCode.INVALID_ARGUMENT),
    (InvalidCursorError, grpc.StatusCode.INVALID_ARGUMENT),
    (InvalidPageSizeError, grpc.StatusCode.INVALID_ARGUMENT),
    (UnauthenticatedError, grpc.StatusCode.UNAUTHENTICATED),
    (RefreshTokenInvalidError, grpc.StatusCode.UNAUTHENTICATED),
    (RefreshTokenExpiredError, grpc.StatusCode.UNAUTHENTICATED),
    (PermissionDeniedError, grpc.StatusCode.PERMISSION_DENIED),
    (UserNotFoundError, grpc.StatusCode.NOT_FOUND),
    (InvalidEmailError, grpc.StatusCode.INVALID_ARGUMENT),
    (InvalidNicknameError, grpc.StatusCode.INVALID_ARGUMENT),
    (WeakPasswordError, grpc.StatusCode.INVALID_ARGUMENT),
    (UserAlreadyRegisterError, grpc.StatusCode.ALREADY_EXISTS),
    (InvalidCredentialsError, grpc.StatusCode.UNAUTHENTICATED),
    (UserNotActiveError, grpc.StatusCode.PERMISSION_DENIED),
]


def find_status_code(error: Exception) -> grpc.StatusCode | None:
    for error_type, status_code in ERROR_CODES:
        if isinstance(error, error_type):
            return status_code
    return None


def grpc_errors[S, Req, Resp](
    method: Callable[[S, Req, Context], Awaitable[Resp]],
) -> Callable[[S, Req, Context], Awaitable[Resp]]:
    @wraps(method)
    async def wrapper(self: S, request: Req, context: Context) -> Resp:
        try:
            return await method(self, request, context)
        except grpc.aio.AbortError:
            raise
        except Exception as e:
            status_code = find_status_code(e)
            if status_code is None:
                logger.exception("Unhandled error in %s", method.__name__)
                await context.abort(grpc.StatusCode.INTERNAL, "Internal server error.")
            else:
                context.set_trailing_metadata(
                    (("jurion-error-code", ERROR_METADATA.get(type(e), "VALIDATION_ERROR")),)
                )
                await context.abort(status_code, str(e))
            raise

    return wrapper
