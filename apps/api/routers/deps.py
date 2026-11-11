"""Gemeinsame Router-Helfer."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.db.models import Soldat
from apps.security.auth import CurrentUser


async def get_owned(session: AsyncSession, model, obj_id: uuid.UUID, user: CurrentUser, name: str):
    """Laedt ein Objekt NUR im Mandanten des Aufrufers (BOLA-Schutz zusaetzlich zu RLS)."""
    obj = (await session.execute(
        select(model).where(model.id == obj_id, model.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if obj is None:
        raise HTTPException(404, f"{name} nicht gefunden")
    return obj


async def soldat_of_user(session: AsyncSession, user: CurrentUser) -> Soldat:
    s = (await session.execute(
        select(Soldat).where(Soldat.tenant_id == user.tenant_id, Soldat.user_sub == user.sub)
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "Kein Soldatendatensatz mit diesem Benutzer verknuepft")
    return s
