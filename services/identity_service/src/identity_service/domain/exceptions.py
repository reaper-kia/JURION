class UserDomainError(Exception):
    pass


class UserAlreadyRegisterError(UserDomainError):
    pass


class InvalidEmailError(UserDomainError):
    pass


class InvalidNicknameError(UserDomainError):
    pass


class WeakPasswordError(UserDomainError):
    pass


class NotFoundUserError(UserDomainError):
    pass
