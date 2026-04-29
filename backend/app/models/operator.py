import enum
import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, Numeric, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    base_efficiency: Mapped[float] = mapped_column(Numeric(5, 2), default=80.0, nullable=False)
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        default=AttendanceStatus.PRESENT,
        nullable=False,
    )
    current_line_id: Mapped[int | None] = mapped_column(ForeignKey("lines.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    line = relationship("Line", back_populates="operators")
    skills = relationship("OperatorSkill", back_populates="operator", cascade="all, delete-orphan")


class OperatorSkill(Base):
    __tablename__ = "operator_skills"
    __table_args__ = (UniqueConstraint("operator_id", "operation_id", name="uq_operator_op"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id", ondelete="CASCADE"), nullable=False)
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    efficiency: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_certified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    operator = relationship("Operator", back_populates="skills")
    operation = relationship("Operation", back_populates="skill_entries")
