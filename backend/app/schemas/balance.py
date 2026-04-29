from datetime import datetime
from pydantic import BaseModel, Field

from ..models.balance import BalanceStatus


class BalanceRequest(BaseModel):
    style_id: int
    line_id: int
    target_output_hour: int = Field(gt=0)
    working_minutes: int = Field(default=480, ge=60, le=1440)
    available_operator_ids: list[int] | None = None  # None => all PRESENT operators on line
    solver_time_limit_s: int | None = None
    explain: bool = False                              # request Claude narrative


class StationLoad(BaseModel):
    station: int
    operator_id: int | None
    operator_name: str | None
    operation_ids: list[int]
    operation_codes: list[str]
    machine_type: str
    cycle_time: float                                  # minutes
    load_pct: float                                    # vs takt
    is_bottleneck: bool


class AssignmentOut(BaseModel):
    station: int
    operator_id: int | None
    operator_name: str | None
    operation_id: int
    operation_code: str
    operation_description: str
    machine_id: int | None
    machine_type: str
    sam: float
    cycle_time: float
    expected_output: int | None

    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    run_id: int
    style_id: int
    line_id: int
    takt_time: float
    theoretical_ops: int
    line_efficiency: float
    balance_loss: float
    bottleneck_station: int | None
    bottleneck_operation_code: str | None
    status: BalanceStatus
    solver: str
    solver_status: str
    assignments: list[AssignmentOut]
    station_loads: list[StationLoad]
    explanation: str | None = None
    warnings: list[str] = []


class BalanceRunOut(BaseModel):
    id: int
    style_id: int
    line_id: int
    target_output_hour: int
    line_efficiency: float | None
    balance_loss: float | None
    status: BalanceStatus
    created_at: datetime

    class Config:
        from_attributes = True


class ExplainRequest(BaseModel):
    question: str | None = None                # custom what-if question


class ExplainResponse(BaseModel):
    run_id: int
    explanation: str
