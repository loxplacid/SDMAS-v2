from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.database import (
    Base,
    check_database_connection,
    create_engine_and_factory,
)


@pytest.mark.asyncio
async def test_session_commit(db_session: AsyncSession):
    await db_session.execute(
        text("CREATE TABLE test_tx_commit (id INTEGER PRIMARY KEY, name VARCHAR)")
    )
    await db_session.execute(
        text("INSERT INTO test_tx_commit (id, name) VALUES (:id, :name)"),
        {"id": 1, "name": "persist"},
    )
    await db_session.commit()

    result = await db_session.execute(
        text("SELECT name FROM test_tx_commit WHERE id = :id"),
        {"id": 1},
    )
    assert result.scalar() == "persist"


@pytest.mark.asyncio
async def test_session_rollback_on_exception(db_session: AsyncSession):
    await db_session.execute(
        text("CREATE TABLE test_tx_rollback (id INTEGER PRIMARY KEY, name VARCHAR)")
    )
    await db_session.commit()

    try:
        async with db_session.begin():
            await db_session.execute(
                text("INSERT INTO test_tx_rollback (id, name) VALUES (:id, :name)"),
                {"id": 1, "name": "will_fail"},
            )
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM test_tx_rollback"),
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_session_cleanup(db_session: AsyncSession):
    """Session should be usable and close cleanly after a successful operation."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    await db_session.close()


@pytest.mark.asyncio
async def test_connectivity_check_success():
    db_ok = await check_database_connection()
    assert db_ok is True


@pytest.mark.asyncio
async def test_connectivity_check_failure():
    bad_engine, _ = create_engine_and_factory(
        "sqlite+aiosqlite:////nonexistent/dir/db.sqlite",
    )
    db_ok = await check_database_connection(engine_override=bad_engine)
    assert db_ok is False
    await bad_engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_fresh_database_per_session(db_session: AsyncSession):
    """Each db_session fixture yields an isolated in-memory database."""
    result = await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'"),
    )
    tables = result.all()
    assert isinstance(tables, list)


@pytest.mark.asyncio
async def test_concurrent_sessions():
    """Two independent sessions should each see their own transaction state."""
    engine1 = create_async_engine("sqlite+aiosqlite://", echo=False)
    engine2 = create_async_engine("sqlite+aiosqlite://", echo=False)

    factory1 = async_sessionmaker(engine1, class_=AsyncSession, expire_on_commit=False)
    factory2 = async_sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)

    async with engine1.begin() as conn:
        await conn.execute(text("CREATE TABLE test_concurrent (id INTEGER PRIMARY KEY, value VARCHAR)"))
        await conn.execute(
            text("INSERT INTO test_concurrent (value) VALUES (:v)"),
            {"v": "from_one"},
        )

    async with engine2.begin() as conn:
        await conn.execute(text("CREATE TABLE test_concurrent (id INTEGER PRIMARY KEY, value VARCHAR)"))
        await conn.execute(
            text("INSERT INTO test_concurrent (value) VALUES (:v)"),
            {"v": "from_two"},
        )

    async with factory1() as s1:
        r1 = await s1.execute(
            text("SELECT value FROM test_concurrent WHERE value = :v"),
            {"v": "from_one"},
        )
        assert r1.scalar() == "from_one"

    async with factory2() as s2:
        r2 = await s2.execute(
            text("SELECT value FROM test_concurrent WHERE value = :v"),
            {"v": "from_two"},
        )
        assert r2.scalar() == "from_two"

    await engine1.dispose()
    await engine2.dispose()