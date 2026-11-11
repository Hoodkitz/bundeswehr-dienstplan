"""SQLAlchemy-Modelle. Alle mandantenbezogenen Tabellen tragen tenant_id (RLS, Spec Kap. 6)."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    security_classification: Mapped[str] = mapped_column(String(50), default="VS-NfD")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Berlin")
    datev_berater_nr: Mapped[str | None] = mapped_column(String(20))
    datev_mandant_nr: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Soldat(Base):
    __tablename__ = "soldaten"
    __table_args__ = (UniqueConstraint("tenant_id", "personalnummer"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    personalnummer: Mapped[str] = mapped_column(String(50))
    dienstgrad: Mapped[str] = mapped_column(String(50))
    vorname: Mapped[str] = mapped_column(String(100))
    nachname: Mapped[str] = mapped_column(String(100))
    qualifikationen: Mapped[list] = mapped_column(JSON, default=list)  # ATNs
    sanitaet_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    user_sub: Mapped[str | None] = mapped_column(String(255), index=True)  # OIDC subject
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Abwesenheit(Base):
    __tablename__ = "abwesenheiten"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    soldat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("soldaten.id", ondelete="CASCADE"), index=True)
    typ: Mapped[str] = mapped_column(String(20))
    start: Mapped[datetime] = mapped_column(DateTime)
    ende: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RosterJob(Base):
    """Aggregat 'dienstplan': Planungslauf inkl. Freigabestatus und Befehls-Audit-Spur."""
    __tablename__ = "roster_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(40))
    zeitraum_start: Mapped[date] = mapped_column(Date)
    zeitraum_ende: Mapped[date] = mapped_column(Date)
    ausnahme_modus: Mapped[str] = mapped_column(String(30), default="keine")
    score: Mapped[str | None] = mapped_column(String(64))
    violations: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    schichten: Mapped[list["Schicht"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Schicht(Base):
    __tablename__ = "schichten"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roster_jobs.id", ondelete="CASCADE"), index=True)
    typ: Mapped[str] = mapped_column(String(30))
    start: Mapped[datetime] = mapped_column(DateTime)
    ende: Mapped[datetime] = mapped_column(DateTime)
    erforderliche_qualifikation: Mapped[str | None] = mapped_column(String(100))
    ort: Mapped[str | None] = mapped_column(String(255))
    soldat_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("soldaten.id", ondelete="SET NULL"), index=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    job: Mapped[RosterJob] = relationship(back_populates="schichten")


class TradeRequest(Base):
    __tablename__ = "trade_requests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    schicht_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schichten.id", ondelete="CASCADE"))
    von_soldat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("soldaten.id", ondelete="CASCADE"))
    an_soldat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("soldaten.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="OFFEN")
    begruendung: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (UniqueConstraint("tenant_id", "seq"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class DatevOutbox(Base):
    """Transactional Outbox (ADR-07)."""
    __tablename__ = "datev_outbox"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roster_jobs.id"))
    format: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | DONE | ERROR
    payload: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[bytes | None] = mapped_column(LargeBinary)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DeletionRegistry(Base):
    """ADR-08: Loeschkaskade statt Soft-Delete. Speichert nur einen Hash des Subjekts."""
    __tablename__ = "deletion_registry"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    hours_retained: Mapped[float] = mapped_column(Float, default=0)
