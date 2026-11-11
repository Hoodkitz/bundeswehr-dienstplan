"""Async DB-Engine und tenant-scoped Sessions (SET LOCAL fuer Postgres-RLS)."""
from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models() -> None:
    from apps.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


_SET = text("SELECT set_config('app.current_tenant_id', :t, true)")


@event.listens_for(Session, "after_begin")
def _apply_tenant_context(session: Session, transaction, connection) -> None:
    """RLS-Kontext in JEDER Transaktion der Session setzen (auch nach commit()).

    set_config(..., true) gilt nur transaktionslokal (kein Leak ueber den Connection-Pool); ohne diesen Hook
    saehe jede Abfrage nach dem ersten commit() keine Zeilen mehr bzw. Inserts verletzten die Policy.
    """
    tid = session.info.get("tenant_id")
    if tid and connection.dialect.name == "postgresql":
        connection.execute(_SET, {"t": tid})


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Mandant fuer diese Session festlegen; gilt fuer die laufende und alle folgenden Transaktionen."""
    session.info["tenant_id"] = str(tenant_id)
    if session.bind.dialect.name == "postgresql" and session.in_transaction():
        await session.execute(_SET, {"t": str(tenant_id)})


async def raw_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
