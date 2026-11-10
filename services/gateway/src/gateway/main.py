import asyncio
import logging
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

import grpc
from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException

from gateway.application.commands import COMMANDS
from gateway.application.core import Dispatcher
from gateway.application.queries import QUERIES
from gateway.config import Settings
from gateway.infra.auth import TokenVerifier
from gateway.infra.grpc import GrpcPort, RpcFailure

log = logging.getLogger("gateway")
COOKIE = "jurion_refresh"
COOKIE_PATH = "/api/v1/auth"


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LoginBody(Body):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RegisterBody(LoginBody):
    nickname: str = Field(min_length=1, max_length=128)


class LogoutBody(Body):
    all_sessions: bool = False


class CreateBody(Body):
    knowledge_base_id: str = Field(min_length=1, max_length=256)


class MessageBody(Body):
    text: str
    as_of_date: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value):
        value = value.strip()
        if not 1 <= len(value) <= 8000:
            raise ValueError("Text must contain 1–8000 characters after trimming")
        return value

    @field_validator("as_of_date")
    @classmethod
    def validate_date(cls, value):
        if value is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Expected YYYY-MM-DD")
            date.fromisoformat(value)
        return value


def error(status, code, *, retryable=False, run_id=None, fields=None):
    item = {
        "code": code,
        "message": code.replace("_", " ").capitalize(),
        "retryable": retryable,
    }
    if run_id:
        item["run_id"] = run_id
    if fields is not None:
        item["field_errors"] = fields
    return JSONResponse({"error": item}, status_code=status)


def create_app(settings=None, ports=None, verifier=None):
    settings = settings or Settings()
    injected_ports = ports

    @asynccontextmanager
    async def lifespan(app):
        channels = []
        if injected_ports is None:
            for target in (
                settings.identity_target,
                settings.conversation_target,
                settings.legal_qa_target,
            ):
                channels.append(
                    grpc.aio.insecure_channel(
                        target, options=(("grpc.enable_retries", 0),)
                    )
                )
            app.state.ports = {
                name: GrpcPort(name, channel, token, settings.rpc_timeout)
                for name, channel, token in zip(
                    ("identity", "conversation", "legal_qa"),
                    channels,
                    (
                        settings.identity_token,
                        settings.conversation_token,
                        settings.legal_qa_token,
                    ),
                )
            }
        else:
            app.state.ports = injected_ports
        app.state.dispatcher = Dispatcher(app.state.ports)
        try:
            yield
        finally:
            for channel in channels:
                await channel.close()

    app = FastAPI(lifespan=lifespan)
    app.state.verifier = verifier or TokenVerifier(
        settings.jwt_public_key, settings.jwt_issuer, settings.jwt_audience
    )
    attempts = defaultdict(deque)

    class TraceAndLimit:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.inner(scope, receive, send)
                return
            start = time.monotonic()
            scope.setdefault("state", {})["request_id"] = str(uuid4())
            scope["state"]["service"] = "-"
            body = bytearray()
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > settings.max_body or not event.get("more_body", False):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {
                        "type": "http.request",
                        "body": bytes(body),
                        "more_body": False,
                    }
                return await receive()

            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append(
                        (b"x-request-id", scope["state"]["request_id"].encode())
                    )
                    if scope["path"].startswith("/api/v1/auth/"):
                        headers.append((b"cache-control", b"no-store"))
                    message["headers"] = headers
                    route = scope.get("route")
                    log.info(
                        "request_id=%s method=%s route=%s status=%s service=%s duration_ms=%.1f",
                        scope["state"]["request_id"],
                        scope["method"],
                        getattr(route, "path", "<unmatched>"),
                        message["status"],
                        scope["state"]["service"],
                        (time.monotonic() - start) * 1000,
                    )
                await send(message)

            if len(body) > settings.max_body:
                await error(413, "PAYLOAD_TOO_LARGE")(scope, replay, send_with_headers)
            else:
                await self.inner(scope, replay, send_with_headers)

    app.add_middleware(TraceAndLimit)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        return error(
            422,
            "VALIDATION_ERROR",
            fields=[
                {
                    "field": ".".join(str(x) for x in item["loc"] if x != "body"),
                    "message": item["msg"],
                }
                for item in exc.errors()
            ],
        )

    @app.exception_handler(RpcFailure)
    async def rpc_handler(request, exc):
        response = error(
            exc.status, exc.code, retryable=exc.retryable, run_id=exc.run_id
        )
        if request.url.path.endswith("/auth/refresh") and exc.code == "REFRESH_INVALID":
            response.delete_cookie(
                COOKIE,
                path=COOKIE_PATH,
                secure=settings.cookie_secure,
                httponly=True,
                samesite="lax",
            )
        return response

    @app.exception_handler(Exception)
    async def internal_handler(request, exc):
        log.error(
            "request_id=%s service=%s unexpected_error=%s",
            request.state.request_id,
            request.state.service,
            type(exc).__name__,
        )
        return error(500, "INTERNAL_ERROR")

    @app.exception_handler(HTTPException)
    async def http_handler(request, exc):
        return error(
            exc.status_code,
            "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR",
        )

    def actor(request, permission=None):
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or not auth[7:]:
            raise RpcFailure(401, "AUTH_REQUIRED")
        try:
            result = app.state.verifier.verify(auth[7:], request.state.request_id)
        except ValueError:
            raise RpcFailure(401, "AUTH_REQUIRED") from None
        if permission and permission not in result.permissions:
            raise RpcFailure(403, "FORBIDDEN")
        return result

    def origin(request):
        value = request.headers.get("origin")
        if not value:
            referer = urlsplit(request.headers.get("referer", ""))
            value = (
                f"{referer.scheme}://{referer.netloc}"
                if referer.scheme and referer.netloc
                else ""
            )
        if value != settings.public_origin:
            raise RpcFailure(403, "FORBIDDEN")

    def rate_limit(request):
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        queue = attempts[key]
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= settings.auth_rate_limit:
            raise RpcFailure(429, "RATE_LIMITED", True)
        queue.append(now)
        if len(attempts) > 10000:
            for k in list(attempts):
                if not attempts[k] or attempts[k][-1] <= now - 60:
                    del attempts[k]

    async def dispatch(request, service, method, data=None, verified=None, query=False):
        request.state.service = service
        return await app.state.dispatcher.dispatch(
            (QUERIES if query else COMMANDS)[method](
                service, method, request.state.request_id, verified, data or {}
            )
        )

    def set_cookie(result, status):
        token = result.pop("_refresh_token")
        expires = result.pop("_refresh_expires_at")
        response = JSONResponse(result, status_code=status)
        response.set_cookie(
            COOKIE,
            token,
            max_age=max(0, int(expires - time.time())),
            path=COOKIE_PATH,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
        )
        return response

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        async def check(port):
            try:
                return await asyncio.wait_for(
                    port.ready(), timeout=settings.rpc_timeout
                )
            except (TimeoutError, grpc.RpcError, OSError):
                return False

        ok = all(
            await asyncio.gather(*(check(port) for port in app.state.ports.values()))
        )
        return JSONResponse(
            {"status": "ready" if ok else "not_ready"}, status_code=200 if ok else 503
        )

    @app.post("/api/v1/auth/register")
    async def register(request: Request, body: RegisterBody):
        origin(request)
        rate_limit(request)
        return set_cookie(
            await dispatch(request, "identity", "Register", body.model_dump()), 201
        )

    @app.post("/api/v1/auth/login")
    async def login(request: Request, body: LoginBody):
        origin(request)
        rate_limit(request)
        return set_cookie(
            await dispatch(request, "identity", "Login", body.model_dump()), 200
        )

    @app.post("/api/v1/auth/refresh")
    async def refresh(request: Request):
        origin(request)
        token = request.cookies.get(COOKIE)
        if not token:
            raise RpcFailure(401, "REFRESH_INVALID")
        return set_cookie(
            await dispatch(
                request, "identity", "RefreshToken", {"refresh_token": token}
            ),
            200,
        )

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request, body: LogoutBody | None = None):
        origin(request)
        all_sessions = body.all_sessions if body else False
        verified = actor(request) if all_sessions else None
        token = request.cookies.get(COOKIE, "")
        if token or all_sessions:
            try:
                await dispatch(
                    request,
                    "identity",
                    "Logout",
                    {"refresh_token": token, "all_sessions": all_sessions},
                    verified,
                )
            except RpcFailure as exc:
                if exc.code != "REFRESH_INVALID":
                    raise
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE,
            path=COOKIE_PATH,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/api/v1/auth/me")
    async def me(request: Request):
        return await dispatch(
            request, "identity", "GetMe", verified=actor(request), query=True
        )

    @app.get("/api/v1/knowledge-bases")
    async def bases(request: Request):
        return await dispatch(
            request,
            "legal_qa",
            "ListKnowledgeBases",
            verified=actor(request, "sources:read"),
            query=True,
        )

    @app.post("/api/v1/conversations", status_code=201)
    async def create_conversation(request: Request, body: CreateBody):
        return await dispatch(
            request,
            "conversation",
            "CreateConversation",
            body.model_dump(),
            actor(request, "conversations:use"),
        )

    @app.get("/api/v1/conversations")
    async def conversations(
        request: Request,
        limit: int = Query(20, ge=1, le=50),
        cursor: str | None = Query(None, min_length=1, max_length=1024),
    ):
        return await dispatch(
            request,
            "conversation",
            "ListConversations",
            {"limit": limit, "cursor": cursor},
            actor(request, "conversations:use"),
            True,
        )

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    async def messages(
        request: Request,
        conversation_id: str,
        limit: int = Query(30, ge=1, le=100),
        before_seq: int | None = Query(None, ge=1, le=4294967295),
    ):
        resource_id(conversation_id)
        return await dispatch(
            request,
            "conversation",
            "ListMessages",
            {
                "conversation_id": conversation_id,
                "limit": limit,
                "before_seq": before_seq,
            },
            actor(request, "conversations:use"),
            True,
        )

    def resource_id(value):
        if (
            not value
            or len(value) > 256
            or any(ord(c) < 32 or c in "/\\" for c in value)
        ):
            raise RpcFailure(422, "VALIDATION_ERROR")

    def key(value):
        try:
            UUID(value)
        except (ValueError, TypeError):
            raise RpcFailure(422, "VALIDATION_ERROR") from None
        return value

    def run_response(run):
        if run["state"] == "failed":
            item = run["error"] or {}
            status = {
                "MODEL_UNAVAILABLE": 503,
                "SERVICE_UNAVAILABLE": 503,
                "ANSWER_TIMEOUT": 504,
                "UPSTREAM_TIMEOUT": 504,
            }.get(item.get("code"), 502)
            return JSONResponse(
                {"error": {**item, "run_id": run["run_id"]}}, status_code=status
            )
        return JSONResponse(run, status_code=202 if run["state"] == "running" else 200)

    @app.post("/api/v1/conversations/{conversation_id}/messages")
    async def send(
        request: Request,
        conversation_id: str,
        body: MessageBody,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ):
        resource_id(conversation_id)
        result = await dispatch(
            request,
            "conversation",
            "SendMessage",
            {
                "conversation_id": conversation_id,
                "idempotency_key": key(idempotency_key),
                **body.model_dump(),
            },
            actor(request, "conversations:use"),
        )
        return run_response(result)

    @app.get("/api/v1/runs/{run_id}")
    async def get_run(request: Request, run_id: str):
        resource_id(run_id)
        return await dispatch(
            request,
            "conversation",
            "GetRun",
            {"run_id": run_id},
            actor(request, "conversations:use"),
            True,
        )

    @app.post("/api/v1/runs/{run_id}/retry")
    async def retry(
        request: Request,
        run_id: str,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ):
        resource_id(run_id)
        return run_response(
            await dispatch(
                request,
                "conversation",
                "RetryRun",
                {"run_id": run_id, "idempotency_key": key(idempotency_key)},
                actor(request, "conversations:use"),
            )
        )

    @app.get("/api/v1/sources/{snapshot_id}/chunks/{chunk_id}")
    async def source_chunk(request: Request, snapshot_id: str, chunk_id: str):
        resource_id(snapshot_id)
        resource_id(chunk_id)
        return await dispatch(
            request,
            "legal_qa",
            "GetSourceChunk",
            {"snapshot_id": snapshot_id, "chunk_id": chunk_id},
            actor(request, "sources:read"),
            True,
        )

    @app.get("/api/v1/sources/{snapshot_id}/files/{file_id}")
    async def source_file(request: Request, snapshot_id: str, file_id: str):
        resource_id(snapshot_id)
        resource_id(file_id)
        result = await dispatch(
            request,
            "legal_qa",
            "GetSourceFile",
            {"snapshot_id": snapshot_id, "file_id": file_id},
            actor(request, "sources:read"),
            True,
        )
        media = (
            "text/plain"
            if result["media_type"].split(";", 1)[0].strip().lower() == "text/plain"
            else "application/octet-stream"
        )
        return Response(
            result["content"],
            media_type=media,
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(result["name"], safe="")
            },
        )

    return app


app = create_app()
