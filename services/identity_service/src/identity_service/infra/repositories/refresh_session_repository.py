from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.applications.exceptions import RefreshSessionNotFoundError
from identity_service.applications.ports.repositories import RefreshSessionRepository
from identity_service.domain.entities import RefreshSession
from identity_service.infra.database.models import RefreshSessionModel


class SQLAlchemyRefreshSessionRepository(RefreshSessionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, session: RefreshSession) -> None:
        self._session.add(self._to_model(session))
        await self._session.flush()

    async def save(self, session: RefreshSession) -> None:
        stmt = select(RefreshSessionModel).where(RefreshSessionModel.id == session.id)

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise RefreshSessionNotFoundError(f"Refresh session {session.id} not found")

        model.revoked_at = session.revoked_at
        model.replaced_by_session_id = session.replaced_by_session_id

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        stmt = select(RefreshSessionModel).where(RefreshSessionModel.token_hash == token_hash)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_token_hash_for_update(
        self,
        token_hash: str,
    ) -> RefreshSession | None:
        stmt = (
            select(RefreshSessionModel)
            .where(RefreshSessionModel.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        model = (await self._session.execute(stmt)).scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def revoke_family(
        self,
        family_id: UUID,
        revoked_at: datetime,
    ) -> None:
        stmt = (
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.family_id == family_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

        await self._session.execute(stmt)

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        revoked_at: datetime,
    ) -> None:
        stmt = (
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.user_id == user_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

        await self._session.execute(stmt)

    @staticmethod
    def _to_model(session: RefreshSession) -> RefreshSessionModel:
        return RefreshSessionModel(
            id=session.id,
            user_id=session.user_id,
            family_id=session.family_id,
            token_hash=session.token_hash,
            expires_at=session.expires_at,
            created_at=session.created_at,
            revoked_at=session.revoked_at,
            replaced_by_session_id=session.replaced_by_session_id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
        )

    @staticmethod
    def _to_domain(model: RefreshSessionModel) -> RefreshSession:
        return RefreshSession(
            id=model.id,
            user_id=model.user_id,
            family_id=model.family_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            created_at=model.created_at,
            revoked_at=model.revoked_at,
            replaced_by_session_id=model.replaced_by_session_id,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
        )
