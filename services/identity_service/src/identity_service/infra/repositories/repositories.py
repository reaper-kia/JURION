from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.applications.exceptions import UserNotFoundError
from identity_service.applications.pagination import UserCursor
from identity_service.applications.ports.repositories import UserReadRepository, UserRepository
from identity_service.applications.results.read_models import UserReadModel
from identity_service.domain.entities import User, UserRole, UserStatus
from identity_service.domain.exceptions import UserAlreadyRegisterError
from identity_service.domain.value_objects import Email, Nickname
from identity_service.infra.database.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(self._to_model(user))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505" and "ix_users_email" in str(exc.orig):
                raise UserAlreadyRegisterError("Email already exists") from exc
            raise

    async def save(self, user: User) -> None:
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise UserNotFoundError(f"User {user.id} not found")

        model.email = user.email.value
        model.nickname = user.nickname.value
        model.password_hash = user.password_hash
        model.password_algorithm = user.password_algorithm
        model.role = user.role
        model.status = user.status
        model.updated_at = user.updated_at
        model.password_changed_at = user.password_changed_at

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_domain(model)

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_domain(model)

    @staticmethod
    def _to_model(user: User) -> UserModel:
        return UserModel(
            id=user.id,
            email=user.email.value,
            nickname=user.nickname.value,
            password_hash=user.password_hash,
            password_algorithm=user.password_algorithm,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            password_changed_at=user.password_changed_at,
        )

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=Email(model.email),
            nickname=Nickname(model.nickname),
            password_hash=model.password_hash,
            password_algorithm=model.password_algorithm,
            role=UserRole(model.role),
            status=UserStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            password_changed_at=model.password_changed_at,
        )


class SQLAlchemyUserReadRepository(UserReadRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserReadModel | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_read_model(model)

    async def get_by_email(self, email: Email) -> UserReadModel | None:
        stmt = select(UserModel).where(UserModel.email == email.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_read_model(model)

    async def list_users(
        self,
        *,
        limit: int = 50,
        after: UserCursor | None = None,
        status: UserStatus | None = None,
        role: UserRole | None = None,
    ) -> list[UserReadModel]:
        stmt = select(UserModel)

        if status is not None:
            stmt = stmt.where(UserModel.status == status)

        if role is not None:
            stmt = stmt.where(UserModel.role == role)

        if after:
            stmt = stmt.where(
                or_(
                    UserModel.created_at > after.created_at,
                    and_(
                        UserModel.created_at == after.created_at,
                        UserModel.id > after.user_id,
                    ),
                )
            )

        stmt = stmt.order_by(UserModel.created_at.asc(), UserModel.id.asc()).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_read_model(raw) for raw in models]

    @staticmethod
    def _to_read_model(model: UserModel) -> UserReadModel:
        return UserReadModel(
            id=model.id,
            email=model.email,
            nickname=model.nickname,
            role=model.role.value,
            status=model.status.value,
            created_at=model.created_at,
            updated_at=model.updated_at,
            password_changed_at=model.password_changed_at,
        )
