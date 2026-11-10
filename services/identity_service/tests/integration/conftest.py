import os
from collections.abc import AsyncIterator
from importlib import import_module

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Importing the current infrastructure creates its configured engine immediately.
# A non-routable fallback lets pytest collect skipped integration tests without a .env file.
os.environ.setdefault(
    "ACCESS_TOKEN_PRIVATE_KEY_PATH",
    "unused-test-private.pem",
)

os.environ.setdefault(
    "DATABASE_URL",
    TEST_DATABASE_URL or "postgresql+asyncpg://unused:unused@127.0.0.1:1/unused_test",
)


def validated_test_database_url() -> str:
    if TEST_DATABASE_URL is None:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")

    database_name = make_url(TEST_DATABASE_URL).database or ""

    if "test" not in database_name.lower():
        pytest.fail("Refusing to recreate a database whose name does not contain 'test'")

    return TEST_DATABASE_URL


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = validated_test_database_url()
    import_module("identity_service.infra.database.models")
    from identity_service.infra.database.base import Base

    engine = create_async_engine(database_url, pool_pre_ping=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    try:
        yield session_factory
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()
