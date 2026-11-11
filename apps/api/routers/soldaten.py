import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routers.deps import get_owned
from apps.api.schemas import AbwesenheitCreate, AbwesenheitOut, SoldatCreate, SoldatOut, SoldatUpdate
from apps.core.permissions import Permission as P
from apps.db.models import Abwesenheit, Soldat
from apps.security.auth import CurrentUser, get_db, require
from apps.services import audit

router = APIRouter(prefix="/api/v1", tags=["soldaten"])


@router.post("/soldaten", response_model=SoldatOut, status_code=201)
async def create_soldat(req: SoldatCreate, user: CurrentUser = Depends(require(P.SOLDAT_WRITE)),
                        db: AsyncSession = Depends(get_db)):
    s = Soldat(tenant_id=user.tenant_id, **req.model_dump(mode="json"))
    db.add(s)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "Personalnummer oder Login-Kennung ist bereits vergeben")
    await audit.append(db, user.tenant_id, "soldat.created", user.sub, {"soldat_id": s.id})
    await db.commit()
    return s


@router.get("/soldaten", response_model=list[SoldatOut])
async def list_soldaten(qualifikation: str | None = None, user: CurrentUser = Depends(require(P.SOLDAT_READ)),
                        db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Soldat).where(Soldat.tenant_id == user.tenant_id)
                             .order_by(Soldat.nachname, Soldat.vorname))).scalars().all()
    if qualifikation:
        rows = [r for r in rows if qualifikation in (r.qualifikationen or [])]
    return rows


@router.get("/soldaten/{soldat_id}", response_model=SoldatOut)
async def get_soldat(soldat_id: uuid.UUID, user: CurrentUser = Depends(require(P.SOLDAT_READ)),
                     db: AsyncSession = Depends(get_db)):
    return await get_owned(db, Soldat, soldat_id, user, "Soldat")


@router.patch("/soldaten/{soldat_id}", response_model=SoldatOut)
async def update_soldat(soldat_id: uuid.UUID, req: SoldatUpdate, user: CurrentUser = Depends(require(P.SOLDAT_WRITE)),
                        db: AsyncSession = Depends(get_db)):
    s = await get_owned(db, Soldat, soldat_id, user, "Soldat")
    changes = req.model_dump(exclude_unset=True, mode="json")
    for k, v in changes.items():
        setattr(s, k, v)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "Login-Kennung ist bereits einem anderen Soldaten zugeordnet")
    await audit.append(db, user.tenant_id, "soldat.updated", user.sub, {"soldat_id": s.id, "felder": sorted(changes)})
    await db.commit()
    return s


@router.post("/abwesenheiten", response_model=AbwesenheitOut, status_code=201)
async def create_abwesenheit(req: AbwesenheitCreate, user: CurrentUser = Depends(require(P.ABWESENHEIT_WRITE)),
                             db: AsyncSession = Depends(get_db)):
    await get_owned(db, Soldat, req.soldat_id, user, "Soldat")
    a = Abwesenheit(tenant_id=user.tenant_id, **req.model_dump())
    db.add(a)
    await db.flush()
    # Kein Diagnose-/Gesundheitsdetail ins Audit (Datensparsamkeit)
    await audit.append(db, user.tenant_id, "abwesenheit.created", user.sub, {"abwesenheit_id": a.id})
    await db.commit()
    return a


@router.get("/abwesenheiten", response_model=list[AbwesenheitOut])
async def list_abwesenheiten(soldat_id: uuid.UUID | None = None, user: CurrentUser = Depends(require(P.ABWESENHEIT_READ)),
                             db: AsyncSession = Depends(get_db)):
    q = select(Abwesenheit).where(Abwesenheit.tenant_id == user.tenant_id)
    if soldat_id:
        q = q.where(Abwesenheit.soldat_id == soldat_id)
    return (await db.execute(q.order_by(Abwesenheit.start))).scalars().all()
