"""Async DB-Engine und tenant-scoped Sessions (SET LOCAL fuer Postgres-RLS)."""
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models() -> None:
    from apps.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Transaktionslokal; verhindert Kontext-Leaks bei Connection-Pool-Wiederverwendung."""
    if session.bind.dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": tenant_id})


async def raw_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
