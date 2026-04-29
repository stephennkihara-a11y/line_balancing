from pydantic import BaseModel, Field

from ..models.operator import AttendanceStatus


class SkillEntry(BaseModel):
    operation_id: int
    efficiency: float = Field(ge=0, le=200)
    is_certified: bool = True


class OperatorCreate(BaseModel):
    employee_code: str = Field(max_length=60)
    name: str = Field(max_length=160)
    grade: int = Field(default=1, ge=1, le=5)
    base_efficiency: float = Field(default=80.0, ge=0, le=200)
    current_line_id: int | None = None
    attendance_status: AttendanceStatus = AttendanceStatus.PRESENT
    skills: list[SkillEntry] = []


class OperatorUpdate(BaseModel):
    name: str | None = None
    grade: int | None = None
    base_efficiency: float | None = None
    current_line_id: int | None = None
    attendance_status: AttendanceStatus | None = None
    is_active: bool | None = None
    skills: list[SkillEntry] | None = None


class SkillOut(BaseModel):
    operation_id: int
    efficiency: float
    is_certified: bool

    class Config:
        from_attributes = True


class OperatorOut(BaseModel):
    id: int
    employee_code: str
    name: str
    grade: int
    base_efficiency: float
    current_line_id: int | None
    attendance_status: AttendanceStatus
    is_active: bool
    skills: list[SkillOut] = []

    class Config:
        from_attributes = True
