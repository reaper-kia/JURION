from urllib.parse import quote

import grpc
from common.v1 import common_pb2
from conversation.v1 import conversation_service_pb2 as conversation
from conversation.v1 import conversation_service_pb2_grpc as conversation_grpc
from google.protobuf.json_format import MessageToDict
from grpc_health.v1 import health_pb2, health_pb2_grpc
from identity.v1 import identity_service_pb2 as identity
from identity.v1 import identity_service_pb2_grpc as identity_grpc
from legal_qa.v1 import legal_qa_service_pb2 as legal_qa
from legal_qa.v1 import legal_qa_service_pb2_grpc as legal_qa_grpc

from gateway.application.core import Command


class RpcFailure(Exception):
    def __init__(self, status, code, retryable=False, run_id=None):
        self.status, self.code, self.retryable, self.run_id = (
            status,
            code,
            retryable,
            run_id,
        )


def map_error(exc, connectivity=None):
    meta = dict(exc.trailing_metadata() or ())
    status = exc.code()
    mapping = {
        grpc.StatusCode.INVALID_ARGUMENT: (422, "VALIDATION_ERROR"),
        grpc.StatusCode.UNAUTHENTICATED: (401, "AUTH_REQUIRED"),
        grpc.StatusCode.PERMISSION_DENIED: (403, "FORBIDDEN"),
        grpc.StatusCode.NOT_FOUND: (404, "NOT_FOUND"),
        grpc.StatusCode.ALREADY_EXISTS: (409, "CONFLICT"),
        grpc.StatusCode.FAILED_PRECONDITION: (409, "CONFLICT"),
        grpc.StatusCode.RESOURCE_EXHAUSTED: (429, "RATE_LIMITED"),
        grpc.StatusCode.UNAVAILABLE: (503, "SERVICE_UNAVAILABLE"),
        grpc.StatusCode.DEADLINE_EXCEEDED: (504, "UPSTREAM_TIMEOUT"),
    }
    http, code = mapping.get(status, (502, "UPSTREAM_ERROR"))
    allowed = {
        "VALIDATION_ERROR",
        "AUTH_REQUIRED",
        "INVALID_CREDENTIALS",
        "REFRESH_INVALID",
        "FORBIDDEN",
        "NOT_FOUND",
        "RUN_IN_PROGRESS",
        "IDEMPOTENCY_CONFLICT",
        "RETRY_NOT_AVAILABLE",
        "EMAIL_ALREADY_EXISTS",
        "RATE_LIMITED",
        "MODEL_UNAVAILABLE",
        "SERVICE_UNAVAILABLE",
        "ANSWER_TIMEOUT",
        "UPSTREAM_TIMEOUT",
        "UPSTREAM_ERROR",
    }
    upstream_code = meta.get("jurion-error-code", "")
    if upstream_code == "SERVICE_UNAUTHENTICATED":
        http, code = 502, "UPSTREAM_ERROR"
    elif upstream_code in allowed:
        code = upstream_code
    if (
        status == grpc.StatusCode.DEADLINE_EXCEEDED
        and connectivity is not None
        and connectivity != grpc.ChannelConnectivity.READY
        and not upstream_code
        and not meta.get("jurion-run-id")
    ):
        return RpcFailure(503, "SERVICE_UNAVAILABLE", retryable=True)
    return RpcFailure(
        http, code, meta.get("jurion-retryable") == "true", meta.get("jurion-run-id")
    )


def as_dict(message):
    return MessageToDict(
        message,
        preserving_proto_field_name=True,
        always_print_fields_with_no_presence=True,
    )


def convert_message(message):
    result = as_dict(message)
    result["role"] = result["role"].removeprefix("MESSAGE_ROLE_").lower()
    if result["role"] == "user":
        result.pop("answer", None)
    elif "answer" in result:
        answer = result["answer"]
        answer["outcome"] = answer["outcome"].removeprefix("OUTCOME_").lower()
        answer.setdefault("clarification_question", None)
    return result


def convert_run(run):
    result = {
        "run_id": run.run_id,
        "conversation_id": run.conversation_id,
        "state": conversation.RunState.Name(run.state)
        .removeprefix("RUN_STATE_")
        .lower(),
        "user_message": convert_message(run.user_message),
        "assistant_message": None,
        "error": None,
    }
    if run.HasField("assistant_message"):
        result["assistant_message"] = convert_message(run.assistant_message)
    if run.HasField("error"):
        result["error"] = as_dict(run.error)
        if not result["error"].get("field_errors"):
            result["error"].pop("field_errors", None)
    return result


class GrpcPort:
    def __init__(self, kind, channel, token, timeout):
        self.kind, self.channel, self.token, self.timeout = (
            kind,
            channel,
            token,
            timeout,
        )
        self.module, stub = {
            "identity": (identity, identity_grpc.IdentityServiceStub),
            "conversation": (conversation, conversation_grpc.ConversationServiceStub),
            "legal_qa": (legal_qa, legal_qa_grpc.LegalQaServiceStub),
        }[kind]
        self.stub = stub(channel)

    async def ready(self):
        response = await health_pb2_grpc.HealthStub(self.channel).Check(
            health_pb2.HealthCheckRequest(),
            timeout=self.timeout,
            metadata=(("x-jurion-service-token", self.token),),
        )
        return response.status == health_pb2.HealthCheckResponse.SERVING

    async def call(self, operation: Command):
        actor = operation.actor
        data = dict(operation.data)
        if self.kind == "identity":
            context = identity.RequestContext(request_id=operation.request_id)
            if actor:
                context.actor_identity_user_id = str(actor.user_id)
                context.permissions.extend(sorted(actor.permissions))
            data["context"] = context
        else:
            data["actor"] = common_pb2.ActorContext(
                request_id=operation.request_id,
                user_id=str(actor.user_id),
                permissions=sorted(actor.permissions),
            )
        request = getattr(self.module, operation.method + "Request")(
            **{k: v for k, v in data.items() if v is not None}
        )
        try:
            response = await getattr(self.stub, operation.method)(
                request,
                timeout=self.timeout,
                metadata=(("x-jurion-service-token", self.token),),
            )
        except grpc.aio.AioRpcError as exc:
            raise map_error(exc, self.channel.get_state()) from exc
        method = operation.method
        if method in ("Register", "Login", "RefreshToken"):
            tokens = response.tokens
            result = {
                "access_token": tokens.access_token,
                "access_token_expires_at": tokens.access_token_expires_at.ToJsonString(),
                "_refresh_token": tokens.refresh_token,
                "_refresh_expires_at": tokens.refresh_token_expires_at.ToDatetime().timestamp(),
            }
            if method != "RefreshToken":
                result["user"] = self.user(response.user)
            return result
        if method == "GetMe":
            return {"user": self.user(response.user)}
        if method == "Logout":
            return None
        if method in ("SendMessage", "RetryRun", "GetRun"):
            return convert_run(response.run)
        if method == "CreateConversation":
            return as_dict(response.conversation)
        if method == "ListMessages":
            return {
                "conversation": as_dict(response.conversation),
                "items": [convert_message(x) for x in response.items],
                "next_before_seq": response.next_before_seq
                if response.HasField("next_before_seq")
                else None,
                "latest_run_id": response.latest_run_id
                if response.HasField("latest_run_id")
                else None,
            }
        if method == "ListConversations":
            return {
                "items": [as_dict(x) for x in response.items],
                "next_cursor": response.next_cursor
                if response.HasField("next_cursor")
                else None,
            }
        if method == "GetSourceChunk":
            result = as_dict(response)
            result["version_label"] = (
                response.version_label if response.HasField("version_label") else None
            )
            result["provision_label"] = (
                response.provision_label
                if response.HasField("provision_label")
                else None
            )
            result["file"]["url"] = (
                f"/api/v1/sources/{quote(response.snapshot_id, safe='')}/files/{quote(response.file.id, safe='')}"
            )
            return result
        if method == "GetSourceFile":
            return {
                "name": response.file.name,
                "media_type": response.file.media_type,
                "content": response.content,
            }
        return as_dict(response)

    @staticmethod
    def user(user):
        result = as_dict(user)
        result["role"] = result["role"].removeprefix("USER_ROLE_").lower()
        result["status"] = result["status"].removeprefix("USER_STATUS_").lower()
        return result
