from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from identity_service.applications.ports.access_token import AccessTokenClaims, AccessTokenIssuer
from identity_service.applications.ports.refresh_token import RefreshTokenService
from identity_service.applications.results.authentication import TokenPairResult
from identity_service.domain.entities import RefreshSession, User
from identity_service.domain.permissions import ROLE_PERMISSIONS


@dataclass(frozen=True)
class CreatedTokenPair:
    refresh_session: RefreshSession
    tokens: TokenPairResult


@dataclass
class TokenPairFactory:
    refresh_tokens: RefreshTokenService
    access_tokens: AccessTokenIssuer
    refresh_token_ttl: timedelta

    def create(self, user: User, now: datetime, family_id: UUID | None = None) -> CreatedTokenPair:

        raw_refresh_token = self.refresh_tokens.generate()
        refresh_token_hash = self.refresh_tokens.hash(raw_refresh_token)
        refresh_token_expires_at = now + self.refresh_token_ttl

        session_family_id = family_id if family_id else uuid4()

        refresh_session = RefreshSession(
            user_id=user.id,
            family_id=session_family_id,
            token_hash=refresh_token_hash,
            expires_at=refresh_token_expires_at,
        )

        claims = AccessTokenClaims(
            user_id=user.id,
            session_id=refresh_session.id,
            family_id=refresh_session.family_id,
            role=user.role,
            permissions=ROLE_PERMISSIONS[user.role],
        )

        issued_access_token = self.access_tokens.issue(
            claims=claims,
            now=now,
        )

        tokens_pair_result = TokenPairResult(
            access_token=issued_access_token.value,
            refresh_token=raw_refresh_token,
            access_token_expire_at=issued_access_token.expires_at,
            refresh_token_expire_at=refresh_token_expires_at,
        )

        return CreatedTokenPair(
            refresh_session=refresh_session,
            tokens=tokens_pair_result,
        )
