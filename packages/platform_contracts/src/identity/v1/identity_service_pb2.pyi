import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UserRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER_ROLE_UNSPECIFIED: _ClassVar[UserRole]
    USER_ROLE_LAWYER: _ClassVar[UserRole]
    USER_ROLE_ADMIN: _ClassVar[UserRole]

class UserStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER_STATUS_UNSPECIFIED: _ClassVar[UserStatus]
    USER_STATUS_ACTIVE: _ClassVar[UserStatus]
    USER_STATUS_BLOCKED: _ClassVar[UserStatus]
    USER_STATUS_DELETED: _ClassVar[UserStatus]
USER_ROLE_UNSPECIFIED: UserRole
USER_ROLE_LAWYER: UserRole
USER_ROLE_ADMIN: UserRole
USER_STATUS_UNSPECIFIED: UserStatus
USER_STATUS_ACTIVE: UserStatus
USER_STATUS_BLOCKED: UserStatus
USER_STATUS_DELETED: UserStatus

class RequestContext(_message.Message):
    __slots__ = ("request_id", "actor_identity_user_id", "permissions")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ACTOR_IDENTITY_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    actor_identity_user_id: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, request_id: _Optional[str] = ..., actor_identity_user_id: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ...) -> None: ...

class UserSnapshot(_message.Message):
    __slots__ = ("user_id", "email", "nickname", "role", "status", "created_at", "updated_at")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    email: str
    nickname: str
    role: UserRole
    status: UserStatus
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, user_id: _Optional[str] = ..., email: _Optional[str] = ..., nickname: _Optional[str] = ..., role: _Optional[_Union[UserRole, str]] = ..., status: _Optional[_Union[UserStatus, str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class TokenPair(_message.Message):
    __slots__ = ("access_token", "refresh_token", "access_token_expires_at", "refresh_token_expires_at")
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    access_token: str
    refresh_token: str
    access_token_expires_at: _timestamp_pb2.Timestamp
    refresh_token_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, access_token: _Optional[str] = ..., refresh_token: _Optional[str] = ..., access_token_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., refresh_token_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RegisterRequest(_message.Message):
    __slots__ = ("context", "email", "nickname", "password")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    email: str
    nickname: str
    password: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., email: _Optional[str] = ..., nickname: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class RegisterResponse(_message.Message):
    __slots__ = ("user", "tokens")
    USER_FIELD_NUMBER: _ClassVar[int]
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    user: UserSnapshot
    tokens: TokenPair
    def __init__(self, user: _Optional[_Union[UserSnapshot, _Mapping]] = ..., tokens: _Optional[_Union[TokenPair, _Mapping]] = ...) -> None: ...

class LoginRequest(_message.Message):
    __slots__ = ("context", "email", "password")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    email: str
    password: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., email: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LoginResponse(_message.Message):
    __slots__ = ("user", "tokens")
    USER_FIELD_NUMBER: _ClassVar[int]
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    user: UserSnapshot
    tokens: TokenPair
    def __init__(self, user: _Optional[_Union[UserSnapshot, _Mapping]] = ..., tokens: _Optional[_Union[TokenPair, _Mapping]] = ...) -> None: ...

class RefreshTokenRequest(_message.Message):
    __slots__ = ("context", "refresh_token")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    refresh_token: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., refresh_token: _Optional[str] = ...) -> None: ...

class RefreshTokenResponse(_message.Message):
    __slots__ = ("tokens",)
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    tokens: TokenPair
    def __init__(self, tokens: _Optional[_Union[TokenPair, _Mapping]] = ...) -> None: ...

class LogoutRequest(_message.Message):
    __slots__ = ("context", "refresh_token", "all_sessions")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ALL_SESSIONS_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    refresh_token: str
    all_sessions: bool
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., refresh_token: _Optional[str] = ..., all_sessions: _Optional[bool] = ...) -> None: ...

class LogoutResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMeRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ...) -> None: ...

class GetMeResponse(_message.Message):
    __slots__ = ("user",)
    USER_FIELD_NUMBER: _ClassVar[int]
    user: UserSnapshot
    def __init__(self, user: _Optional[_Union[UserSnapshot, _Mapping]] = ...) -> None: ...

class GetUserRequest(_message.Message):
    __slots__ = ("context", "user_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    user_id: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetUserResponse(_message.Message):
    __slots__ = ("user",)
    USER_FIELD_NUMBER: _ClassVar[int]
    user: UserSnapshot
    def __init__(self, user: _Optional[_Union[UserSnapshot, _Mapping]] = ...) -> None: ...

class ListUsersRequest(_message.Message):
    __slots__ = ("context", "role", "status", "limit", "cursor")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    role: UserRole
    status: UserStatus
    limit: int
    cursor: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., role: _Optional[_Union[UserRole, str]] = ..., status: _Optional[_Union[UserStatus, str]] = ..., limit: _Optional[int] = ..., cursor: _Optional[str] = ...) -> None: ...

class ListUsersResponse(_message.Message):
    __slots__ = ("users", "next_cursor")
    USERS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    users: _containers.RepeatedCompositeFieldContainer[UserSnapshot]
    next_cursor: str
    def __init__(self, users: _Optional[_Iterable[_Union[UserSnapshot, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class BlockUserRequest(_message.Message):
    __slots__ = ("context", "user_id", "reason")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    context: RequestContext
    user_id: str
    reason: str
    def __init__(self, context: _Optional[_Union[RequestContext, _Mapping]] = ..., user_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class BlockUserResponse(_message.Message):
    __slots__ = ("user",)
    USER_FIELD_NUMBER: _ClassVar[int]
    user: UserSnapshot
    def __init__(self, user: _Optional[_Union[UserSnapshot, _Mapping]] = ...) -> None: ...
