import datetime

from common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MessageRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MESSAGE_ROLE_UNSPECIFIED: _ClassVar[MessageRole]
    MESSAGE_ROLE_USER: _ClassVar[MessageRole]
    MESSAGE_ROLE_ASSISTANT: _ClassVar[MessageRole]

class Outcome(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OUTCOME_UNSPECIFIED: _ClassVar[Outcome]
    OUTCOME_ANSWERED: _ClassVar[Outcome]
    OUTCOME_PARTIALLY_ANSWERED: _ClassVar[Outcome]
    OUTCOME_NEEDS_CLARIFICATION: _ClassVar[Outcome]
    OUTCOME_INSUFFICIENT_EVIDENCE: _ClassVar[Outcome]
    OUTCOME_INVALID_PREMISE: _ClassVar[Outcome]
    OUTCOME_OUT_OF_SCOPE: _ClassVar[Outcome]
    OUTCOME_DISALLOWED: _ClassVar[Outcome]
MESSAGE_ROLE_UNSPECIFIED: MessageRole
MESSAGE_ROLE_USER: MessageRole
MESSAGE_ROLE_ASSISTANT: MessageRole
OUTCOME_UNSPECIFIED: Outcome
OUTCOME_ANSWERED: Outcome
OUTCOME_PARTIALLY_ANSWERED: Outcome
OUTCOME_NEEDS_CLARIFICATION: Outcome
OUTCOME_INSUFFICIENT_EVIDENCE: Outcome
OUTCOME_INVALID_PREMISE: Outcome
OUTCOME_OUT_OF_SCOPE: Outcome
OUTCOME_DISALLOWED: Outcome

class HistoryMessage(_message.Message):
    __slots__ = ("role", "text")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    role: MessageRole
    text: str
    def __init__(self, role: _Optional[_Union[MessageRole, str]] = ..., text: _Optional[str] = ...) -> None: ...

class AnswerRequest(_message.Message):
    __slots__ = ("request_id", "run_id", "knowledge_base_id", "messages", "as_of_date", "deadline_at")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_BASE_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    AS_OF_DATE_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_AT_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    run_id: str
    knowledge_base_id: str
    messages: _containers.RepeatedCompositeFieldContainer[HistoryMessage]
    as_of_date: str
    deadline_at: _timestamp_pb2.Timestamp
    def __init__(self, request_id: _Optional[str] = ..., run_id: _Optional[str] = ..., knowledge_base_id: _Optional[str] = ..., messages: _Optional[_Iterable[_Union[HistoryMessage, _Mapping]]] = ..., as_of_date: _Optional[str] = ..., deadline_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Citation(_message.Message):
    __slots__ = ("chunk_id", "label", "quote")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    QUOTE_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    label: str
    quote: str
    def __init__(self, chunk_id: _Optional[str] = ..., label: _Optional[str] = ..., quote: _Optional[str] = ...) -> None: ...

class VerifiedClaim(_message.Message):
    __slots__ = ("text", "citations")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    text: str
    citations: _containers.RepeatedCompositeFieldContainer[Citation]
    def __init__(self, text: _Optional[str] = ..., citations: _Optional[_Iterable[_Union[Citation, _Mapping]]] = ...) -> None: ...

class AnswerResponse(_message.Message):
    __slots__ = ("snapshot_id", "outcome", "text", "claims", "missing_information", "clarification_question", "provider", "model")
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_FIELD_NUMBER: _ClassVar[int]
    MISSING_INFORMATION_FIELD_NUMBER: _ClassVar[int]
    CLARIFICATION_QUESTION_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    snapshot_id: str
    outcome: Outcome
    text: str
    claims: _containers.RepeatedCompositeFieldContainer[VerifiedClaim]
    missing_information: _containers.RepeatedScalarFieldContainer[str]
    clarification_question: str
    provider: str
    model: str
    def __init__(self, snapshot_id: _Optional[str] = ..., outcome: _Optional[_Union[Outcome, str]] = ..., text: _Optional[str] = ..., claims: _Optional[_Iterable[_Union[VerifiedClaim, _Mapping]]] = ..., missing_information: _Optional[_Iterable[str]] = ..., clarification_question: _Optional[str] = ..., provider: _Optional[str] = ..., model: _Optional[str] = ...) -> None: ...

class KnowledgeBase(_message.Message):
    __slots__ = ("id", "title")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ...) -> None: ...

class ListKnowledgeBasesRequest(_message.Message):
    __slots__ = ("actor",)
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ...) -> None: ...

class ListKnowledgeBasesResponse(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[KnowledgeBase]
    def __init__(self, items: _Optional[_Iterable[_Union[KnowledgeBase, _Mapping]]] = ...) -> None: ...

class GetSourceChunkRequest(_message.Message):
    __slots__ = ("actor", "snapshot_id", "chunk_id")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    snapshot_id: str
    chunk_id: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., snapshot_id: _Optional[str] = ..., chunk_id: _Optional[str] = ...) -> None: ...

class SourceFileRef(_message.Message):
    __slots__ = ("id", "name", "media_type")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    media_type: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., media_type: _Optional[str] = ...) -> None: ...

class GetSourceChunkResponse(_message.Message):
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
    file: SourceFileRef
    def __init__(self, chunk_id: _Optional[str] = ..., snapshot_id: _Optional[str] = ..., document_title: _Optional[str] = ..., version_label: _Optional[str] = ..., provision_label: _Optional[str] = ..., text: _Optional[str] = ..., line_start: _Optional[int] = ..., line_end: _Optional[int] = ..., file: _Optional[_Union[SourceFileRef, _Mapping]] = ...) -> None: ...

class GetSourceFileRequest(_message.Message):
    __slots__ = ("actor", "snapshot_id", "file_id")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_ID_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    snapshot_id: str
    file_id: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., snapshot_id: _Optional[str] = ..., file_id: _Optional[str] = ...) -> None: ...

class GetSourceFileResponse(_message.Message):
    __slots__ = ("file", "content")
    FILE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    file: SourceFileRef
    content: bytes
    def __init__(self, file: _Optional[_Union[SourceFileRef, _Mapping]] = ..., content: _Optional[bytes] = ...) -> None: ...
