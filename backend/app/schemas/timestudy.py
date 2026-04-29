from datetime import datetime
from pydantic import BaseModel, Field


class TimeStudyCreate(BaseModel):
    operation_id: int
    operator_id: int | None = None
    cycle_seconds: float = Field(gt=0)
    rating: float = Field(default=100, ge=0, le=200)
    allowance: float = Field(default=15, ge=0, le=100)
    sample_size: int = Field(default=1, ge=1, le=100)
    note: str | None = None


class TimeStudyOut(BaseModel):
    id: int
    operation_id: int
    operator_id: int | None
    cycle_seconds: float
    rating: float
    allowance: float
    captured_sam: float | None
    sample_size: int
    note: str | None
    captured_at: datetime
    operation_code: str | None = None
    operation_description: str | None = None
    standard_sam: float | None = None
    deviation_pct: float | None = None      # captured vs standard

    class Config:
        from_attributes = True


class TimeStudyAggregate(BaseModel):
    operation_id: int
    operation_code: str
    standard_sam: float
    captured_avg: float
    captured_min: float
    captured_max: float
    sample_count: int
    deviation_pct: float
    flag: str                                # "ok" | "high" | "low"
