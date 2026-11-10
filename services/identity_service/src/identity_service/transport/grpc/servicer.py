import logging
from uuid import UUID

from identity_service.applications.commands.refresh_token import RefreshTokenCommand
from identity_service.applications.context import RequestContext
from identity_service.applications.handlers.session_and_users import (
    BlockUser,
    GetMe,
    GetUser,
    ListUsers,
    Logout,
)
from identity_service.domain.entities import UserRole, UserStatus


def request_context(context):
    return RequestContext(
        context.request_id,
        UUID(context.actor_identity_user_id)
        if context.HasField("actor_identity_user_id")
        else None,
        frozenset(context.permissions),
    )


from identity.v1 import identity_service_pb2 as pb
from identity.v1 import identity_service_pb2_grpc as pb_grpc

from identity_service.applications.commands.login_user import LoginUserCommand
from identity_service.applications.commands.register_user import RegisterUserCommand
from identity_service.applications.mediator import Mediator
from identity_service.transport.grpc.errors import Context, grpc_errors
from identity_service.transport.grpc.mappers import tokens_to_proto, user_to_proto

logger = logging.getLogger(__name__)


class IdentityServicer(pb_grpc.IdentityServiceServicer):
    def __init__(self, mediator: Mediator) -> None:
        self._mediator = mediator

    @grpc_errors
    async def Register(self, request: pb.RegisterRequest, context: Context) -> pb.RegisterResponse:
        logger.info("Register request_id=%s", request.context.request_id)

        command = RegisterUserCommand(
            nickname=request.nickname,
            email=request.email,
            password=request.password,
        )
        result = await self._mediator.send(command)
        return pb.RegisterResponse(
            user=user_to_proto(result.user),
            tokens=tokens_to_proto(result.tokens),
        )

    @grpc_errors
    async def Login(self, request: pb.LoginRequest, context: Context) -> pb.LoginResponse:
        logger.info("Login request_id=%s", request.context.request_id)

        command = LoginUserCommand(
            email=request.email,
            password=request.password,
        )

        result = await self._mediator.send(command)

        return pb.LoginResponse(
            user=user_to_proto(result.user),
            tokens=tokens_to_proto(result.tokens),
        )

    @grpc_errors
    async def RefreshToken(self, request, context):
        result = await self._mediator.send(RefreshTokenCommand(request.refresh_token))
        return pb.RefreshTokenResponse(tokens=tokens_to_proto(result))

    @grpc_errors
    async def Logout(self, request, context):
        await self._mediator.send(
            Logout(request_context(request.context), request.refresh_token, request.all_sessions)
        )
        return pb.LogoutResponse()

    @grpc_errors
    async def GetMe(self, request, context):
        user = await self._mediator.send(GetMe(request_context(request.context)))
        return pb.GetMeResponse(user=user_to_proto(user))

    @grpc_errors
    async def GetUser(self, request, context):
        user = await self._mediator.send(
            GetUser(request_context(request.context), UUID(request.user_id))
        )
        return pb.GetUserResponse(user=user_to_proto(user))

    @grpc_errors
    async def ListUsers(self, request, context):
        roles = {pb.USER_ROLE_LAWYER: UserRole.LAWYER, pb.USER_ROLE_ADMIN: UserRole.ADMIN}
        statuses = {
            pb.USER_STATUS_ACTIVE: UserStatus.ACTIVE,
            pb.USER_STATUS_BLOCKED: UserStatus.BLOCKED,
            pb.USER_STATUS_DELETED: UserStatus.DELETED,
        }
        if (request.HasField("role") and request.role not in roles) or (
            request.HasField("status") and request.status not in statuses
        ):
            raise ValueError("Invalid filter")
        result = await self._mediator.send(
            ListUsers(
                request_context(request.context),
                request.limit,
                request.cursor or None,
                roles.get(request.role) if request.HasField("role") else None,
                statuses.get(request.status) if request.HasField("status") else None,
            )
        )
        return pb.ListUsersResponse(
            users=[user_to_proto(user) for user in result.users],
            next_cursor=result.next_cursor or "",
        )

    @grpc_errors
    async def BlockUser(self, request, context):
        user = await self._mediator.send(
            BlockUser(request_context(request.context), UUID(request.user_id), request.reason)
        )
        return pb.BlockUserResponse(user=user_to_proto(user))
