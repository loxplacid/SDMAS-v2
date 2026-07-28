from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.database import Base, async_session_factory


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_session_factory_creates_session():
    assert async_session_factory is not None
    async with async_session_factory() as session:
        assert isinstance(session, AsyncSession)


@pytest.mark.asyncio
async def test_database_connection(db_session: AsyncSession):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_transaction_commit(db_session: AsyncSession):
    class TestModel(Base):
        __tablename__ = "test_commit"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    async with db_session.begin():
        db_session.add(TestModel(name="test"))
    result = await db_session.execute(
        text("SELECT name FROM test_commit WHERE name = :name"),
        {"name": "test"},
    )
    assert result.scalar() == "test"


@pytest.mark.asyncio
async def test_transaction_rollback(db_session: AsyncSession):
    class TestRollback(Base):
        __tablename__ = "test_rollback"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    async with db_session.begin():
        db_session.add(TestRollback(name="will_fail"))
        raise RuntimeError("force rollback")

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM test_rollback"),
    )
    assert result.scalar() == 0
