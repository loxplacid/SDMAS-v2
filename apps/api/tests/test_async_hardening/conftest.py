"""Shared fixtures for the async-hardening test suite.

The suite proves the multi-instance / multi-worker guarantees of the
jobs, scheduler, outbox and notification infrastructure:

* job claims are atomic (CAS) so concurrent workers never double-run
* identity keys make enqueue idempotent (duplicate job execution)
* retry → dead-letter state transitions work end-to-end
* tenant context is restored per job / per outbox delivery
* events survive worker/API restarts and replay idempotently
* the scheduler never double-enqueues a cycle
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database import Base

# Import all models so Base.metadata can resolve cross-module foreign keys
from app.domains.institution.models import (  # noqa: F401
    Institution,
    Campus,
)
from app.domains.auth.models import User  # noqa: F401
from app.domains.jobs.models import Job  # noqa: F401
from app.domains.billing.models import (  # noqa: F401
    Plan,
    Subscription,
    Invoice,
)
from app.domains.communications.models import (  # noqa: F401
    CommunicationMessage,
    MessageRecipient,
    MessageSchedule,
)
from app.domains.events.outbox import OutboxEvent  # noqa: F401
from app.domains.notifications.models import Notification  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh in-memory SQLite with all metadata, one session per test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker, None]:
    """A session factory bound to the test DB (for spawning worker sessions)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _load_job_modules():
    """Load every registered job implementation before each test.

    The jobs registry is process-global; loading the periodic jobs (and the
    report export job) ensures ``get_job_class`` resolves them during job
    execution tests.
    """
    from app.domains.jobs.loader import load_all_jobs

    load_all_jobs()
    yield
