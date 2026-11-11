"""Alembic environment (async engine; URL from DATABASE_URL / MIGRATION_DATABASE_URL)."""
import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from apps.core.config import settings
from apps.db.models import Base

target_metadata = Base.metadata
URL = os.environ.get("MIGRATION_DATABASE_URL") or settings.DATABASE_URL


def run_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(URL)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
