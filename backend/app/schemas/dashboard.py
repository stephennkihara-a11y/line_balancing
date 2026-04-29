from datetime import datetime
from pydantic import BaseModel, Field

from ..models.operations import RebalanceTrigger


# ---------- Hourly production ---------------------------------------
class HourlyProductionCreate(BaseModel):
    line_id: int
    run_id: int | None = None
    hour_slot: int = Field(ge=1, le=24)
    target: int = Field(ge=0)
    actual: int = Field(ge=0)
    note: str | None = None


class HourlyProductionOut(BaseModel):
    id: int
    line_id: int
    run_id: int | None
    captured_at: datetime
    hour_slot: int
    target: int
    actual: int
    note: str | None

    class Config:
        from_attributes = True


# ---------- WIP ------------------------------------------------------
class StationWIPCreate(BaseModel):
    run_id: int
    station: int
    wip_units: int = Field(ge=0)
    threshold: int = Field(default=25, ge=1)


class StationWIPOut(BaseModel):
    id: int
    run_id: int
    station: int
    captured_at: datetime
    wip_units: int
    threshold: int

    class Config:
        from_attributes = True


# ---------- Re-balance triggers / diffs -----------------------------
class RebalanceCheckResponse(BaseModel):
    line_id: int
    run_id: int | None
    triggered: bool
    trigger: RebalanceTrigger | None
    reasons: list[str]
    target_output_hour: int
    last_hour_actual: int | None
    deviation_pct: float | None
    absent_operator_ids: list[int] = []
    broken_machine_ids: list[int] = []


class RebalanceProposeRequest(BaseModel):
    line_id: int
    trigger: RebalanceTrigger = RebalanceTrigger.MANUAL
    target_output_hour: int | None = None       # if None, reuse last run's
    explain: bool = False


class StationDiff(BaseModel):
    station: int
    operator_before: str | None
    operator_after: str | None
    op_codes_before: list[str]
    op_codes_after: list[str]
    cycle_before: float
    cycle_after: float
    load_pct_before: float
    load_pct_after: float
    is_bottleneck_after: bool


class RebalanceDiffResponse(BaseModel):
    event_id: int
    previous_run_id: int | None
    new_run_id: int
    trigger: RebalanceTrigger
    eff_before: float | None
    eff_after: float
    output_before: int | None
    output_after: int
    delta_eff: float
    delta_output: int
    diffs: list[StationDiff]
    explanation: str | None = None
    warnings: list[str] = []


class RebalanceAcceptRequest(BaseModel):
    accepted: bool


# ---------- Bottleneck dashboard -------------------------------------
class WIPAlert(BaseModel):
    run_id: int
    station: int
    wip_units: int
    threshold: int
    severity: str                    # "warning" | "critical"


class StationHeatPoint(BaseModel):
    station: int
    operator_name: str | None
    op_codes: list[str]
    machine_type: str
    cycle_time: float
    load_pct: float
    is_bottleneck: bool
    wip_units: int | None = None
    wip_threshold: int | None = None


class BottleneckRootCause(BaseModel):
    cause: str                                     # e.g. "skill_gap", "machine", "method", "layout"
    detail: str
    suggestion: str


class BottleneckDashboardResponse(BaseModel):
    line_id: int
    run_id: int | None
    line_efficiency: float | None
    balance_loss: float | None
    target_output_hour: int | None
    heat: list[StationHeatPoint]
    bottleneck_station: int | None
    bottleneck_op_code: str | None
    wip_alerts: list[WIPAlert]
    root_causes: list[BottleneckRootCause]
    last_hour: HourlyProductionOut | None
