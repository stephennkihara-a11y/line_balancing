import enum
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class MachineType(str, enum.Enum):
    SNLS = "SNLS"          # Single Needle Lock Stitch
    OL = "OL"              # Overlock
    FOA = "FOA"            # Flatlock / Feed of Arm
    BARTACK = "BARTACK"
    BUTTON = "BUTTON"
    BUTTONHOLE = "BUTTONHOLE"
    IRON = "IRON"
    MANUAL = "MANUAL"


class MachineStatus(str, enum.Enum):
    WORKING = "WORKING"
    IDLE = "IDLE"
    BREAKDOWN = "BREAKDOWN"
    MAINTENANCE = "MAINTENANCE"


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    type: Mapped[MachineType] = mapped_column(Enum(MachineType, name="machine_type"), nullable=False)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("lines.id", ondelete="SET NULL"))
    status: Mapped[MachineStatus] = mapped_column(
        Enum(MachineStatus, name="machine_status"), default=MachineStatus.IDLE, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    line = relationship("Line", back_populates="machines")
