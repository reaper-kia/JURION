from datetime import datetime

from google.protobuf.timestamp_pb2 import Timestamp
from identity.v1 import identity_service_pb2 as pb

from identity_service.applications.results.authentication import TokenPairResult
from identity_service.applications.results.read_models import UserReadModel

ROLE_TO_PROTO: dict[str, pb.UserRole] = {
    "lawyer": pb.USER_ROLE_LAWYER,
    "admin": pb.USER_ROLE_ADMIN,
}

STATUS_TO_PROTO: dict[str, pb.UserStatus] = {
    "active": pb.USER_STATUS_ACTIVE,
    "blocked": pb.USER_STATUS_BLOCKED,
    "deleted": pb.USER_STATUS_DELETED,
}


def to_timestamp(value: datetime) -> Timestamp:
    timestamp = Timestamp()
    timestamp.FromDatetime(value)
    return timestamp


def user_to_proto(user: UserReadModel) -> pb.UserSnapshot:
    return pb.UserSnapshot(
        user_id=str(user.id),
        email=user.email,
        nickname=user.nickname,
        role=ROLE_TO_PROTO[user.role],
        status=STATUS_TO_PROTO[user.status],
        created_at=to_timestamp(user.created_at),
        updated_at=to_timestamp(user.updated_at),
    )


def tokens_to_proto(tokens: TokenPairResult) -> pb.TokenPair:
    return pb.TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_token_expires_at=to_timestamp(tokens.access_token_expire_at),
        refresh_token_expires_at=to_timestamp(tokens.refresh_token_expire_at),
    )
