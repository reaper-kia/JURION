from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ActorContext(_message.Message):
    __slots__ = ("request_id", "user_id", "permissions")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    user_id: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, request_id: _Optional[str] = ..., user_id: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ...) -> None: ...

class FieldError(_message.Message):
    __slots__ = ("field", "message")
    FIELD_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    field: str
    message: str
    def __init__(self, field: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ApiError(_message.Message):
    __slots__ = ("code", "message", "retryable", "run_id", "field_errors")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RETRYABLE_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    FIELD_ERRORS_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    retryable: bool
    run_id: str
    field_errors: _containers.RepeatedCompositeFieldContainer[FieldError]
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ..., retryable: _Optional[bool] = ..., run_id: _Optional[str] = ..., field_errors: _Optional[_Iterable[_Union[FieldError, _Mapping]]] = ...) -> None: ...
