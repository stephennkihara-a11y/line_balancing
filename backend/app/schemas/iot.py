from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class TelemetryEvent(BaseModel):
    machine_code: str
    is_running: bool
    rpm: int | None = None
    captured_at: datetime | None = None
    payload: dict[str, Any] | None = None


class TelemetryBatch(BaseModel):
    events: list[TelemetryEvent] = Field(min_length=1, max_length=10_000)


class TelemetryAck(BaseModel):
    received: int
    accepted: int
    rejected: int
    unknown_machines: list[str] = []


class MachineUtilisation(BaseModel):
    machine_id: int
    machine_code: str
    type: str
    line_id: int | None
    sample_count: int
    running_pct: float
    avg_rpm: float | None
    last_seen: datetime | None
    last_state: str
