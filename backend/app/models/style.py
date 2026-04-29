from datetime import datetime

from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey, Text, UniqueConstraint, CheckConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .machine import MachineType


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    style_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    garment_type: Mapped[str | None] = mapped_column(String(80))
    total_sam: Mapped[float | None] = mapped_column(Numeric(10, 3))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    operations = relationship(
        "Operation", back_populates="style", cascade="all, delete-orphan", order_by="Operation.sequence"
    )


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("style_id", "op_code", name="uq_style_opcode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    style_id: Mapped[int] = mapped_column(ForeignKey("styles.id", ondelete="CASCADE"), nullable=False)
    op_code: Mapped[str] = mapped_column(String(60), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    sam: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    machine_type: Mapped[MachineType] = mapped_column(Enum(MachineType, name="machine_type"), nullable=False)
    skill_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    section: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    style = relationship("Style", back_populates="operations")
    skill_entries = relationship("OperatorSkill", back_populates="operation", cascade="all, delete-orphan")

    predecessors = relationship(
        "OperationPrecedence",
        foreign_keys="OperationPrecedence.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
    )
    successors = relationship(
        "OperationPrecedence",
        foreign_keys="OperationPrecedence.predecessor_id",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )


class OperationPrecedence(Base):
    __tablename__ = "operation_precedence"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_precedence_pair"),
        CheckConstraint("predecessor_id <> successor_id", name="ck_no_self_precedence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    style_id: Mapped[int] = mapped_column(ForeignKey("styles.id", ondelete="CASCADE"), nullable=False)
    predecessor_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    successor_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)

    predecessor = relationship("Operation", foreign_keys=[predecessor_id], back_populates="successors")
    successor = relationship("Operation", foreign_keys=[successor_id], back_populates="predecessors")
