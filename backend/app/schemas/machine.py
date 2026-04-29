from pydantic import BaseModel, Field

from ..models.machine import MachineType, MachineStatus


class MachineCreate(BaseModel):
    machine_code: str = Field(max_length=60)
    type: MachineType
    line_id: int | None = None
    status: MachineStatus = MachineStatus.IDLE
    notes: str | None = None


class MachineUpdate(BaseModel):
    type: MachineType | None = None
    line_id: int | None = None
    status: MachineStatus | None = None
    notes: str | None = None


class MachineOut(BaseModel):
    id: int
    machine_code: str
    type: MachineType
    line_id: int | None
    status: MachineStatus
    notes: str | None

    class Config:
        from_attributes = True
