import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import grpc
import httpx
import jwt
import pytest
from conversation.v1 import conversation_service_pb2 as cp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from gateway.application.core import Dispatcher, VerifiedActor
from gateway.config import Settings
from gateway.infra.auth import TokenVerifier
from gateway.infra.grpc import RpcFailure, convert_run, map_error
from gateway.main import create_app
from legal_qa.v1 import legal_qa_service_pb2 as lp


class FakePort:
    def __init__(self):
        self.calls = []
        self.result = {}
        self.failure = None

    async def ready(self):
        return True

    async def call(self, op):
        self.calls.append(op)
        if self.failure:
            raise self.failure
        return dict(self.result) if isinstance(self.result, dict) else self.result


class FakeVerifier:
    def verify(self, token, request_id):
        if token != "valid":
            raise ValueError()
        return VerifiedActor(
            uuid4(),
            "lawyer",
            frozenset({"conversations:use", "sources:read"}),
            request_id,
        )


@pytest.fixture
def env():
    ports = {name: FakePort() for name in ("identity", "conversation", "legal_qa")}
    app = create_app(
        replace(Settings(), public_origin="http://localhost", cookie_secure=False),
        ports,
        FakeVerifier(),
    )
    app.state.ports = ports
    app.state.dispatcher = Dispatcher(ports)

    class Client:
        def __init__(self):
            self.cookies = httpx.Cookies()

        def request(self, method, url, **kwargs):
            async def run():
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://localhost",
                    cookies=self.cookies,
                ) as client:
                    response = await client.request(method, url, **kwargs)
                    self.cookies = client.cookies
                    return response

            return asyncio.run(run())

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

    yield Client(), ports


AUTH = {"Authorization": "Bearer valid"}
ORIGIN = {"Origin": "http://localhost"}


def test_auth_cookie_origin_refresh_and_outage(env):
    client, ports = env
    ports["identity"].result = {
        "access_token": "access",
        "access_token_expires_at": "2026-01-01T00:00:00Z",
        "_refresh_token": "secret",
        "_refresh_expires_at": datetime.now(UTC).timestamp() + 300,
        "user": {},
    }
    body = {"email": "fake@example.test", "password": "password"}
    assert client.post("/api/v1/auth/login", json=body).status_code == 403
    response = client.post("/api/v1/auth/login", json=body, headers=ORIGIN)
    assert response.status_code == 200 and "secret" not in response.text
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "Path=/api/v1/auth" in response.headers["set-cookie"]
    )
    assert response.headers["cache-control"] == "no-store"
    ports["identity"].failure = RpcFailure(503, "SERVICE_UNAVAILABLE")
    response = client.post("/api/v1/auth/refresh", headers=ORIGIN)
    assert response.status_code == 503 and "set-cookie" not in response.headers
    ports["identity"].failure = RpcFailure(401, "REFRESH_INVALID")
    response = client.post("/api/v1/auth/refresh", headers=ORIGIN)
    assert response.status_code == 401 and "Max-Age=0" in response.headers["set-cookie"]


def test_message_validates_and_propagates_verified_actor(env):
    client, ports = env
    ports["conversation"].result = {"state": "running", "run_id": "run_01"}
    key = str(uuid4())
    headers = {
        **AUTH,
        "Idempotency-Key": key,
        "X-User-Id": str(uuid4()),
        "X-Permissions": "users:block",
    }
    url = "/api/v1/conversations/conv_01/messages"
    assert (
        client.post(
            url, headers=headers, json={"text": " hi ", "owner_user_id": "fake"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, headers=headers, json={"text": "hi", "as_of_date": "2024-02-30"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, headers={**headers, "Idempotency-Key": "bad"}, json={"text": "hi"}
        ).status_code
        == 422
    )
    response = client.post(url, headers=headers, json={"text": " hi "})
    assert response.status_code == 202
    operation = ports["conversation"].calls[-1]
    assert operation.data["text"] == "hi" and operation.data["idempotency_key"] == key
    assert operation.actor.permissions == frozenset(
        {"conversations:use", "sources:read"}
    )
    assert operation.actor.request_id == response.headers["x-request-id"]


def test_readiness_permissions_and_validation(env):
    client, _ = env
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/v1/knowledge-bases").status_code == 401
    assert client.get("/api/v1/conversations?limit=51", headers=AUTH).status_code == 422
    assert (
        client.post(
            "/api/v1/auth/logout", headers=ORIGIN, json={"all_sessions": True}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", headers=ORIGIN, content=b"x" * 65537
        ).status_code
        == 413
    )


def test_run_conversion_and_failed_status(env):
    run = cp.AnswerRun(run_id="r", conversation_id="c", state=cp.RUN_STATE_COMPLETED)
    run.user_message.id = "m"
    run.user_message.role = lp.MESSAGE_ROLE_USER
    run.assistant_message.role = lp.MESSAGE_ROLE_ASSISTANT
    run.assistant_message.answer.outcome = lp.OUTCOME_NEEDS_CLARIFICATION
    result = convert_run(run)
    assert result["state"] == "completed" and "answer" not in result["user_message"]
    answer = result["assistant_message"]["answer"]
    assert (
        answer["outcome"] == "needs_clarification"
        and answer["claims"] == []
        and answer["clarification_question"] is None
    )
    client, ports = env
    ports["conversation"].result = {
        "state": "failed",
        "run_id": "r",
        "error": {"code": "ANSWER_TIMEOUT", "message": "Timeout", "retryable": True},
    }
    assert (
        client.post(
            "/api/v1/conversations/c/messages",
            headers={**AUTH, "Idempotency-Key": str(uuid4())},
            json={"text": "q"},
        ).status_code
        == 504
    )
    assert client.get("/api/v1/runs/r", headers=AUTH).status_code == 200


def test_jwt_validates_issuer_audience_algorithm_and_role():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    verifier = TokenVerifier(public, "jurion-identity", "jurion")
    claims = {
        "sub": str(uuid4()),
        "role": "lawyer",
        "permissions": ["sources:read"],
        "iss": "jurion-identity",
        "aud": "jurion",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    assert (
        verifier.verify(jwt.encode(claims, key, algorithm="RS256"), "r").role
        == "lawyer"
    )
    for change in (
        {"aud": "casino"},
        {"iss": "casino"},
        {"role": "player"},
        {"permissions": ["unknown"]},
        {"sub": "invalid"},
    ):
        with pytest.raises(ValueError):
            verifier.verify(
                jwt.encode({**claims, **change}, key, algorithm="RS256"), "r"
            )
    with pytest.raises(ValueError):
        verifier.verify(jwt.encode(claims, "a" * 32, algorithm="HS256"), "r")


def test_service_auth_error_does_not_look_like_user_error():
    class Error:
        def code(self):
            return grpc.StatusCode.UNAUTHENTICATED

        def trailing_metadata(self):
            return (("jurion-error-code", "SERVICE_UNAUTHENTICATED"),)

    result = map_error(Error())
    assert (result.status, result.code) == (502, "UPSTREAM_ERROR")


def test_grpc_adapter_context_deadline_and_file_url():
    from gateway.application.core import Query
    from gateway.infra.grpc import GrpcPort
    from legal_qa.v1 import legal_qa_service_pb2 as pb

    class Call:
        def __init__(self):
            self.request = None
            self.options = None

        async def __call__(self, request, **options):
            self.request, self.options = request, options
            return pb.GetSourceChunkResponse(
                chunk_id="chunk_1",
                snapshot_id="snap 1",
                document_title="Doc",
                text="Text",
                line_start=1,
                line_end=1,
                file=pb.SourceFileRef(
                    id="file 1", name="source.txt", media_type="text/plain"
                ),
            )

    async def run():
        channel = grpc.aio.insecure_channel("localhost:65535")
        port = GrpcPort("legal_qa", channel, "service-secret", 2)
        call = Call()
        port.stub.GetSourceChunk = call
        actor = VerifiedActor(uuid4(), "lawyer", frozenset({"sources:read"}), "trace")
        result = await port.call(
            Query(
                "legal_qa",
                "GetSourceChunk",
                "trace",
                actor,
                {"snapshot_id": "snap 1", "chunk_id": "chunk_1"},
            )
        )
        assert result["file"]["url"] == "/api/v1/sources/snap%201/files/file%201"
        assert result["version_label"] is None and result["provision_label"] is None
        assert call.request.actor.user_id == str(actor.user_id)
        assert call.request.actor.request_id == "trace"
        assert call.options == {
            "timeout": 2,
            "metadata": (("x-jurion-service-token", "service-secret"),),
        }
        await channel.close()

    asyncio.run(run())


def test_grpc_status_mapping():
    class Error:
        def __init__(self, status, metadata=()):
            self.status, self.metadata = status, metadata

        def code(self):
            return self.status

        def trailing_metadata(self):
            return self.metadata

    for status, expected in (
        (grpc.StatusCode.INVALID_ARGUMENT, 422),
        (grpc.StatusCode.UNAUTHENTICATED, 401),
        (grpc.StatusCode.PERMISSION_DENIED, 403),
        (grpc.StatusCode.NOT_FOUND, 404),
        (grpc.StatusCode.ALREADY_EXISTS, 409),
        (grpc.StatusCode.FAILED_PRECONDITION, 409),
        (grpc.StatusCode.RESOURCE_EXHAUSTED, 429),
        (grpc.StatusCode.UNAVAILABLE, 503),
        (grpc.StatusCode.DEADLINE_EXCEEDED, 504),
        (grpc.StatusCode.INTERNAL, 502),
        (grpc.StatusCode.UNKNOWN, 502),
        (grpc.StatusCode.UNIMPLEMENTED, 502),
    ):
        assert map_error(Error(status)).status == expected
    disconnected = map_error(
        Error(grpc.StatusCode.DEADLINE_EXCEEDED),
        grpc.ChannelConnectivity.TRANSIENT_FAILURE,
    )
    assert (disconnected.status, disconnected.code) == (503, "SERVICE_UNAVAILABLE")
    deadline = map_error(
        Error(grpc.StatusCode.DEADLINE_EXCEEDED), grpc.ChannelConnectivity.READY
    )
    assert (deadline.status, deadline.code) == (504, "UPSTREAM_TIMEOUT")
    result = map_error(
        Error(
            grpc.StatusCode.FAILED_PRECONDITION,
            (("jurion-error-code", "RUN_IN_PROGRESS"), ("jurion-run-id", "run_1")),
        )
    )
    assert result.code == "RUN_IN_PROGRESS" and result.run_id == "run_1"


def test_lifecycle_closes_all_channels(monkeypatch):
    from gateway import main

    channels = []

    class Channel:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    def open_channel(target, options):
        channel = Channel()
        channels.append(channel)
        return channel

    monkeypatch.setattr(main.grpc.aio, "insecure_channel", open_channel)
    monkeypatch.setattr(main, "GrpcPort", lambda *args: FakePort())
    app = create_app()

    async def run():
        async with app.router.lifespan_context(app):
            assert len(app.state.ports) == 3
            assert len(channels) == 3 and not any(c.closed for c in channels)
        assert all(c.closed for c in channels)

    asyncio.run(run())


def test_source_file_download_is_authenticated_and_encoded(env):
    client, ports = env
    ports["legal_qa"].result = {
        "name": "источник.txt",
        "media_type": "text/plain; charset=utf-8",
        "content": b"text",
    }
    url = "/api/v1/sources/snap_1/files/file_1"
    assert client.get(url).status_code == 401
    response = client.get(url, headers=AUTH)
    assert response.content == b"text"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "filename*=UTF-8''%D0" in response.headers["content-disposition"]
    assert ports["legal_qa"].calls[-1].data == {
        "snapshot_id": "snap_1",
        "file_id": "file_1",
    }
