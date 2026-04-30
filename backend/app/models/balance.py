import enum
import uuid
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, Numeric, Enum, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class BalanceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class BalanceRun(Base):
    __tablename__ = "balance_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    style_id: Mapped[int] = mapped_column(ForeignKey("styles.id", ondelete="CASCADE"), nullable=False)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id", ondelete="CASCADE"), nullable=False)
    target_output_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    working_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)
    available_operators: Mapped[int] = mapped_column(Integer, nullable=False)
    takt_time: Mapped[float | None] = mapped_column(Numeric(8, 3))
    theoretical_ops: Mapped[int | None] = mapped_column(Integer)
    line_efficiency: Mapped[float | None] = mapped_column(Numeric(5, 2))
    balance_loss: Mapped[float | None] = mapped_column(Numeric(5, 2))
    bottleneck_op_id: Mapped[int | None] = mapped_column(ForeignKey("operations.id", ondelete="SET NULL"))
    status: Mapped[BalanceStatus] = mapped_column(
        Enum(BalanceStatus, name="balance_status"), default=BalanceStatus.DRAFT, nullable=False
    )
    solver: Mapped[str] = mapped_column(String(40), default="cp-sat", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    style = relationship("Style")
    line = relationship("Line")
    bottleneck = relationship("Operation", foreign_keys=[bottleneck_op_id])
    assignments = relationship(
        "BalanceAssignment", back_populates="run", cascade="all, delete-orphan", order_by="BalanceAssignment.station"
    )


class BalanceAssignment(Base):
    __tablename__ = "balance_assignments"
    __table_args__ = (UniqueConstraint("run_id", "operation_id", name="uq_run_op"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("balance_runs.id", ondelete="CASCADE"), nullable=False)
    station: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"))
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id", ondelete="SET NULL"))
    cycle_time: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    expected_output: Mapped[int | None] = mapped_column(Integer)

    run = relationship("BalanceRun", back_populates="assignments")
    operator = relationship("Operator")
    operation = relationship("Operation")
    machine = relationship("Machine")
