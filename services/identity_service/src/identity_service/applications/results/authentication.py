from dataclasses import dataclass
from datetime import datetime

from identity_service.applications.results.read_models import UserReadModel


@dataclass(frozen=True)
class TokenPairResult:
    access_token: str
    refresh_token: str
    access_token_expire_at: datetime
    refresh_token_expire_at: datetime


@dataclass(frozen=True)
class AuthenticationResult:
    user: UserReadModel
    tokens: TokenPairResult
