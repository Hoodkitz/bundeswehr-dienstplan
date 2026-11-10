"""SQLAlchemy models with RLS."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, JSON, Date, Interval
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        {"schema": "public"},
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    security_classification = Column(String(50), default="VS-NfD")
    created_at = Column(DateTime, server_default="NOW()")
    timezone = Column(String(50), default="Europe/Berlin")
    _secret_key = Column("secret_key", String(255), nullable=True)


class Soldat(Base):
    __tablename__ = "soldaten"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    personalnummer = Column(String(50), nullable=False)
    dienstgrad = Column(String(50), nullable=False)
    vorname = Column(String(100), nullable=False)
    nachname = Column(String(100), nullable=False)
    qualifikationen = Column(JSON, default=list)
    arbeitszeitkonto_id = Column(String(100), nullable=True)
    eingestellt = Column(Boolean, default=False)
    eigene_oeffentliche_zustaendigkeit = Column(Boolean, default=False)
    grenzbeschraenkung = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default="NOW()")
    absenzen = relationship("Abwesenheit", back_populates="soldat")
    schichten = relationship("Schicht", back_populates="soldat")
    dienstplaene = relationship("Dienstplan", back_populates="soldat")


class Schicht(Base):
    __tablename__ = "schichten"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    soldat_id = Column(UUID(as_uuid=True), ForeignKey("soldaten.id"), nullable=False)
    schicht_type = Column(String(50), nullable=False)
    start_zeit = Column(DateTime, nullable=False)
    end_zeit = Column(DateTime, nullable=False)
    dienstplan_id = Column(UUID(as_uuid=True), ForeignKey("dienstplaene.id"), nullable=True)
    haushaltsnummer = Column(String(50), nullable=True)
    ort = Column(String(255), nullable=True)
    beschreibung = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default="NOW()")
    soldat = relationship("Soldat", back_populates="schichten")
    dienstplan = relationship("Dienstplan", back_populates="schichten")


class Dienstplan(Base):
    __tablename__ = "dienstplaene"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    planungszeitraum_start = Column(Date, nullable=False)
    planungszeitraum_ende = Column(Date, nullable=False)
    status = Column(String(50), default="DRAFT")
    approver_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, server_default="NOW()")
    published_at = Column(DateTime, nullable=True)
    export_pdf_url = Column(String(500), nullable=True)
    export_xlsx_url = Column(String(500), nullable=True)
    export_ics_url = Column(String(500), nullable=True)
    audit_trail = Column(JSON, default=list)
    soldat = relationship("Soldat", back_populates="dienstplaene")
    schichten = relationship("Schicht", back_populates="dienstplan")


class Abwesenheit(Base):
    __tablename__ = "abwesenheiten"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    soldat_id = Column(UUID(as_uuid=True), ForeignKey("soldaten.id"), nullable=False)
    typ = Column(String(50), nullable=False)  # URLAUF, KREIS, SONSTIGE
    start_datum = Column(Date, nullable=False)
    end_datum = Column(Date, nullable=True)
    begruendung = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default="NOW()")
    soldat = relationship("Soldat", back_populates="absenzen")
