class InvalidCursorError(Exception):
    pass


class InvalidPageSizeError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class RefreshSessionNotFoundError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotActiveError(Exception):
    pass


class RefreshTokenInvalidError(Exception):
    pass


class RefreshTokenExpiredError(Exception):
    pass


class UnauthenticatedError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass
