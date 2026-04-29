"""Phase 2/3 ORM models: hourly production, WIP, re-balance events,
time studies, machine telemetry, ERP external-id mapping."""
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class HourlyProduction(Base):
    __tablename__ = "hourly_production"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("balance_runs.id", ondelete="SET NULL"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    hour_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    actual: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class StationWIP(Base):
    __tablename__ = "station_wip"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("balance_runs.id", ondelete="CASCADE"), nullable=False)
    station: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    wip_units: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, default=25, nullable=False)


class RebalanceTrigger(str, enum.Enum):
    OPERATOR_ABSENT = "OPERATOR_ABSENT"
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    TARGET_CHANGE = "TARGET_CHANGE"
    OUTPUT_DEVIATION = "OUTPUT_DEVIATION"
    MANUAL = "MANUAL"


class RebalanceEvent(Base):
    __tablename__ = "rebalance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id", ondelete="CASCADE"), nullable=False)
    previous_run_id: Mapped[int | None] = mapped_column(ForeignKey("balance_runs.id", ondelete="SET NULL"))
    new_run_id: Mapped[int | None] = mapped_column(ForeignKey("balance_runs.id", ondelete="SET NULL"))
    trigger: Mapped[RebalanceTrigger] = mapped_column(Enum(RebalanceTrigger, name="rebalance_trigger"), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    eff_before: Mapped[float | None] = mapped_column(Numeric(5, 2))
    eff_after: Mapped[float | None] = mapped_column(Numeric(5, 2))
    output_before: Mapped[int | None] = mapped_column(Integer)
    output_after: Mapped[int | None] = mapped_column(Integer)
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TimeStudy(Base):
    __tablename__ = "time_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"))
    captured_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    cycle_seconds: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    rating: Mapped[float] = mapped_column(Numeric(5, 2), default=100, nullable=False)
    allowance: Mapped[float] = mapped_column(Numeric(5, 2), default=15, nullable=False)
    # captured_sam is a generated column server-side; SQLAlchemy reads only.
    captured_sam: Mapped[float | None] = mapped_column(Numeric(8, 3))
    sample_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MachineTelemetry(Base):
    __tablename__ = "machine_telemetry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_running: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rpm: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ErpExternalId(Base):
    __tablename__ = "erp_external_ids"
    __table_args__ = (UniqueConstraint("entity", "local_id", "erp_system", name="uq_erp_local"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    erp_system: Mapped[str] = mapped_column(String(40), default="odoo", nullable=False)
    erp_model: Mapped[str | None] = mapped_column(String(80))
    erp_id: Mapped[str] = mapped_column(String(80), nullable=False)
    last_sync: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
