import datetime

from common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from legal_qa.v1 import legal_qa_service_pb2 as _legal_qa_service_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RunState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RUN_STATE_UNSPECIFIED: _ClassVar[RunState]
    RUN_STATE_RUNNING: _ClassVar[RunState]
    RUN_STATE_COMPLETED: _ClassVar[RunState]
    RUN_STATE_FAILED: _ClassVar[RunState]
RUN_STATE_UNSPECIFIED: RunState
RUN_STATE_RUNNING: RunState
RUN_STATE_COMPLETED: RunState
RUN_STATE_FAILED: RunState

class Conversation(_message.Message):
    __slots__ = ("id", "knowledge_base_id", "title", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_BASE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    knowledge_base_id: str
    title: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., knowledge_base_id: _Optional[str] = ..., title: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Claim(_message.Message):
    __slots__ = ("id", "text", "citations")
    ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    id: str
    text: str
    citations: _containers.RepeatedCompositeFieldContainer[_legal_qa_service_pb2.Citation]
    def __init__(self, id: _Optional[str] = ..., text: _Optional[str] = ..., citations: _Optional[_Iterable[_Union[_legal_qa_service_pb2.Citation, _Mapping]]] = ...) -> None: ...

class Answer(_message.Message):
    __slots__ = ("outcome", "snapshot_id", "claims", "missing_information", "clarification_question")
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_FIELD_NUMBER: _ClassVar[int]
    MISSING_INFORMATION_FIELD_NUMBER: _ClassVar[int]
    CLARIFICATION_QUESTION_FIELD_NUMBER: _ClassVar[int]
    outcome: _legal_qa_service_pb2.Outcome
    snapshot_id: str
    claims: _containers.RepeatedCompositeFieldContainer[Claim]
    missing_information: _containers.RepeatedScalarFieldContainer[str]
    clarification_question: str
    def __init__(self, outcome: _Optional[_Union[_legal_qa_service_pb2.Outcome, str]] = ..., snapshot_id: _Optional[str] = ..., claims: _Optional[_Iterable[_Union[Claim, _Mapping]]] = ..., missing_information: _Optional[_Iterable[str]] = ..., clarification_question: _Optional[str] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("id", "seq", "role", "text", "created_at", "answer")
    ID_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    ANSWER_FIELD_NUMBER: _ClassVar[int]
    id: str
    seq: int
    role: _legal_qa_service_pb2.MessageRole
    text: str
    created_at: _timestamp_pb2.Timestamp
    answer: Answer
    def __init__(self, id: _Optional[str] = ..., seq: _Optional[int] = ..., role: _Optional[_Union[_legal_qa_service_pb2.MessageRole, str]] = ..., text: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., answer: _Optional[_Union[Answer, _Mapping]] = ...) -> None: ...

class AnswerRun(_message.Message):
    __slots__ = ("run_id", "conversation_id", "state", "user_message", "assistant_message", "error")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    USER_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ASSISTANT_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    conversation_id: str
    state: RunState
    user_message: Message
    assistant_message: Message
    error: _common_pb2.ApiError
    def __init__(self, run_id: _Optional[str] = ..., conversation_id: _Optional[str] = ..., state: _Optional[_Union[RunState, str]] = ..., user_message: _Optional[_Union[Message, _Mapping]] = ..., assistant_message: _Optional[_Union[Message, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.ApiError, _Mapping]] = ...) -> None: ...

class CreateConversationRequest(_message.Message):
    __slots__ = ("actor", "knowledge_base_id")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_BASE_ID_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    knowledge_base_id: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., knowledge_base_id: _Optional[str] = ...) -> None: ...

class CreateConversationResponse(_message.Message):
    __slots__ = ("conversation",)
    CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    conversation: Conversation
    def __init__(self, conversation: _Optional[_Union[Conversation, _Mapping]] = ...) -> None: ...

class SendMessageRequest(_message.Message):
    __slots__ = ("actor", "conversation_id", "idempotency_key", "text", "as_of_date")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    AS_OF_DATE_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    conversation_id: str
    idempotency_key: str
    text: str
    as_of_date: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., conversation_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., text: _Optional[str] = ..., as_of_date: _Optional[str] = ...) -> None: ...

class SendMessageResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: AnswerRun
    def __init__(self, run: _Optional[_Union[AnswerRun, _Mapping]] = ...) -> None: ...

class RetryRunRequest(_message.Message):
    __slots__ = ("actor", "run_id", "idempotency_key")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    run_id: str
    idempotency_key: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., run_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class RetryRunResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: AnswerRun
    def __init__(self, run: _Optional[_Union[AnswerRun, _Mapping]] = ...) -> None: ...

class ListConversationsRequest(_message.Message):
    __slots__ = ("actor", "limit", "cursor")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    limit: int
    cursor: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., limit: _Optional[int] = ..., cursor: _Optional[str] = ...) -> None: ...

class ListConversationsResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Conversation]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[Conversation, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class ListMessagesRequest(_message.Message):
    __slots__ = ("actor", "conversation_id", "limit", "before_seq")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    BEFORE_SEQ_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    conversation_id: str
    limit: int
    before_seq: int
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., conversation_id: _Optional[str] = ..., limit: _Optional[int] = ..., before_seq: _Optional[int] = ...) -> None: ...

class ListMessagesResponse(_message.Message):
    __slots__ = ("conversation", "items", "next_before_seq", "latest_run_id")
    CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_BEFORE_SEQ_FIELD_NUMBER: _ClassVar[int]
    LATEST_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    conversation: Conversation
    items: _containers.RepeatedCompositeFieldContainer[Message]
    next_before_seq: int
    latest_run_id: str
    def __init__(self, conversation: _Optional[_Union[Conversation, _Mapping]] = ..., items: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., next_before_seq: _Optional[int] = ..., latest_run_id: _Optional[str] = ...) -> None: ...

class GetRunRequest(_message.Message):
    __slots__ = ("actor", "run_id")
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    actor: _common_pb2.ActorContext
    run_id: str
    def __init__(self, actor: _Optional[_Union[_common_pb2.ActorContext, _Mapping]] = ..., run_id: _Optional[str] = ...) -> None: ...

class GetRunResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: AnswerRun
    def __init__(self, run: _Optional[_Union[AnswerRun, _Mapping]] = ...) -> None: ...
