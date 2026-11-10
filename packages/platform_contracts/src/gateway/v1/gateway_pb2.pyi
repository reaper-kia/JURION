import datetime

from common.v1 import common_pb2 as _common_pb2
from conversation.v1 import conversation_service_pb2 as _conversation_service_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from identity.v1 import identity_service_pb2 as _identity_service_pb2
from legal_qa.v1 import legal_qa_service_pb2 as _legal_qa_service_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RegisterBody(_message.Message):
    __slots__ = ("email", "nickname", "password")
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    email: str
    nickname: str
    password: str
    def __init__(self, email: _Optional[str] = ..., nickname: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LoginBody(_message.Message):
    __slots__ = ("email", "password")
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    email: str
    password: str
    def __init__(self, email: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LogoutBody(_message.Message):
    __slots__ = ("all_sessions",)
    ALL_SESSIONS_FIELD_NUMBER: _ClassVar[int]
    all_sessions: bool
    def __init__(self, all_sessions: _Optional[bool] = ...) -> None: ...

class AccessTokenResponse(_message.Message):
    __slots__ = ("access_token", "access_token_expires_at")
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    access_token: str
    access_token_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, access_token: _Optional[str] = ..., access_token_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AuthResponse(_message.Message):
    __slots__ = ("user", "access_token", "access_token_expires_at")
    USER_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    user: _identity_service_pb2.UserSnapshot
    access_token: str
    access_token_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, user: _Optional[_Union[_identity_service_pb2.UserSnapshot, _Mapping]] = ..., access_token: _Optional[str] = ..., access_token_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class MeResponse(_message.Message):
    __slots__ = ("user",)
    USER_FIELD_NUMBER: _ClassVar[int]
    user: _identity_service_pb2.UserSnapshot
    def __init__(self, user: _Optional[_Union[_identity_service_pb2.UserSnapshot, _Mapping]] = ...) -> None: ...

class CreateConversationBody(_message.Message):
    __slots__ = ("knowledge_base_id",)
    KNOWLEDGE_BASE_ID_FIELD_NUMBER: _ClassVar[int]
    knowledge_base_id: str
    def __init__(self, knowledge_base_id: _Optional[str] = ...) -> None: ...

class SendMessageBody(_message.Message):
    __slots__ = ("text", "as_of_date")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    AS_OF_DATE_FIELD_NUMBER: _ClassVar[int]
    text: str
    as_of_date: str
    def __init__(self, text: _Optional[str] = ..., as_of_date: _Optional[str] = ...) -> None: ...

class KnowledgeBasePage(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_legal_qa_service_pb2.KnowledgeBase]
    def __init__(self, items: _Optional[_Iterable[_Union[_legal_qa_service_pb2.KnowledgeBase, _Mapping]]] = ...) -> None: ...

class ConversationPage(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_conversation_service_pb2.Conversation]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[_conversation_service_pb2.Conversation, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class MessagePage(_message.Message):
    __slots__ = ("conversation", "items", "next_before_seq", "latest_run_id")
    CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_BEFORE_SEQ_FIELD_NUMBER: _ClassVar[int]
    LATEST_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    conversation: _conversation_service_pb2.Conversation
    items: _containers.RepeatedCompositeFieldContainer[_conversation_service_pb2.Message]
    next_before_seq: int
    latest_run_id: str
    def __init__(self, conversation: _Optional[_Union[_conversation_service_pb2.Conversation, _Mapping]] = ..., items: _Optional[_Iterable[_Union[_conversation_service_pb2.Message, _Mapping]]] = ..., next_before_seq: _Optional[int] = ..., latest_run_id: _Optional[str] = ...) -> None: ...

class SourceFile(_message.Message):
    __slots__ = ("id", "name", "media_type", "url")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    media_type: str
    url: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., media_type: _Optional[str] = ..., url: _Optional[str] = ...) -> None: ...

class SourceChunk(_message.Message):
    __slots__ = ("chunk_id", "snapshot_id", "document_title", "version_label", "provision_label", "text", "line_start", "line_end", "file")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_TITLE_FIELD_NUMBER: _ClassVar[int]
    VERSION_LABEL_FIELD_NUMBER: _ClassVar[int]
    PROVISION_LABEL_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    LINE_START_FIELD_NUMBER: _ClassVar[int]
    LINE_END_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    snapshot_id: str
    document_title: str
    version_label: str
    provision_label: str
    text: str
    line_start: int
    line_end: int
    file: SourceFile
    def __init__(self, chunk_id: _Optional[str] = ..., snapshot_id: _Optional[str] = ..., document_title: _Optional[str] = ..., version_label: _Optional[str] = ..., provision_label: _Optional[str] = ..., text: _Optional[str] = ..., line_start: _Optional[int] = ..., line_end: _Optional[int] = ..., file: _Optional[_Union[SourceFile, _Mapping]] = ...) -> None: ...

class ErrorResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.ApiError
    def __init__(self, error: _Optional[_Union[_common_pb2.ApiError, _Mapping]] = ...) -> None: ...
