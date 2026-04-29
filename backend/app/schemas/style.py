from pydantic import BaseModel, Field

from ..models.machine import MachineType


class OperationCreate(BaseModel):
    op_code: str = Field(max_length=60)
    sequence: int = Field(ge=1)
    description: str = Field(max_length=240)
    sam: float = Field(gt=0)
    machine_type: MachineType
    skill_level: int = Field(default=1, ge=1, le=5)
    section: str | None = None
    predecessor_op_codes: list[str] = []


class OperationOut(BaseModel):
    id: int
    op_code: str
    sequence: int
    description: str
    sam: float
    machine_type: MachineType
    skill_level: int
    section: str | None

    class Config:
        from_attributes = True


class PrecedenceCreate(BaseModel):
    predecessor_op_code: str
    successor_op_code: str


class PrecedenceOut(BaseModel):
    predecessor_id: int
    successor_id: int

    class Config:
        from_attributes = True


class StyleCreate(BaseModel):
    style_code: str = Field(max_length=60)
    name: str = Field(max_length=200)
    garment_type: str | None = None
    description: str | None = None
    operations: list[OperationCreate] = []


class StyleUpdate(BaseModel):
    name: str | None = None
    garment_type: str | None = None
    description: str | None = None


class StyleOut(BaseModel):
    id: int
    style_code: str
    name: str
    garment_type: str | None
    total_sam: float | None
    description: str | None

    class Config:
        from_attributes = True


class StyleDetail(StyleOut):
    operations: list[OperationOut] = []
    precedence: list[PrecedenceOut] = []
