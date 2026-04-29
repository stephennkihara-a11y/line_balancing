"""IoT machine telemetry ingestion + utilisation queries.

Designed to accept high-volume sensor batches:
  POST /api/iot/telemetry  { events: [{machine_code, is_running, ...}] }

Calibration: average running_pct per machine type can be cross-checked
against theoretical SAM to flag styles that consistently run slow.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, desc, func
from sqlalchemy.orm import Session

from ..auth.security import get_current_user, require_role
from ..database import get_db
from ..models import Machine, MachineTelemetry, MachineStatus, User, UserRole
from ..schemas.iot import (
    TelemetryBatch, TelemetryAck, MachineUtilisation,
)

router = APIRouter(prefix="/api/iot", tags=["iot"])


@router.post("/telemetry", response_model=TelemetryAck, status_code=202)
def ingest(
    batch: TelemetryBatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(
        UserRole.SUPERVISOR, UserRole.IE, UserRole.PRODUCTION_MANAGER, UserRole.ADMIN,
    )),
) -> TelemetryAck:
    machine_codes = {e.machine_code for e in batch.events}
    machines = (
        db.query(Machine).filter(Machine.machine_code.in_(machine_codes)).all()
    )
    by_code = {m.machine_code: m for m in machines}
    unknown = sorted(machine_codes - set(by_code))

    accepted = 0
    for e in batch.events:
        m = by_code.get(e.machine_code)
        if not m:
            continue
        db.add(MachineTelemetry(
            machine_id=m.id,
            captured_at=e.captured_at or datetime.utcnow(),
            is_running=e.is_running,
            rpm=e.rpm,
            payload=e.payload,
        ))
        # Auto-update machine status: any RUNNING event flips IDLE to WORKING
        if e.is_running and m.status == MachineStatus.IDLE:
            m.status = MachineStatus.WORKING
        elif not e.is_running and m.status == MachineStatus.WORKING:
            m.status = MachineStatus.IDLE
        accepted += 1
    db.commit()

    return TelemetryAck(
        received=len(batch.events),
        accepted=accepted,
        rejected=len(batch.events) - accepted,
        unknown_machines=unknown,
    )


@router.get("/utilisation", response_model=list[MachineUtilisation])
def utilisation(
    line_id: int | None = None,
    minutes: int = Query(60, ge=5, le=1440),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MachineUtilisation]:
    """Average running_pct over the last `minutes` minutes."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    machines_q = db.query(Machine)
    if line_id is not None:
        machines_q = machines_q.filter(Machine.line_id == line_id)
    machines = machines_q.all()
    if not machines:
        return []
    machine_ids = [m.id for m in machines]

    rows = (
        db.query(
            MachineTelemetry.machine_id,
            func.count(MachineTelemetry.id).label("n"),
            func.sum(cast(MachineTelemetry.is_running, Integer)).label("running"),
            func.avg(MachineTelemetry.rpm).label("avg_rpm"),
            func.max(MachineTelemetry.captured_at).label("last_seen"),
        )
        .filter(
            MachineTelemetry.machine_id.in_(machine_ids),
            MachineTelemetry.captured_at >= since,
        )
        .group_by(MachineTelemetry.machine_id)
        .all()
    )
    by_id = {r.machine_id: r for r in rows}

    # Latest state per machine
    latest_state: dict[int, bool] = {}
    for mid in machine_ids:
        last = (
            db.query(MachineTelemetry)
            .filter(MachineTelemetry.machine_id == mid)
            .order_by(desc(MachineTelemetry.captured_at))
            .first()
        )
        if last:
            latest_state[mid] = bool(last.is_running)

    out: list[MachineUtilisation] = []
    for m in machines:
        r = by_id.get(m.id)
        if r and r.n:
            running_pct = round(float(r.running or 0) / float(r.n) * 100, 2)
            avg_rpm = float(r.avg_rpm) if r.avg_rpm is not None else None
            last_seen = r.last_seen
        else:
            running_pct = 0.0
            avg_rpm = None
            last_seen = None
        out.append(MachineUtilisation(
            machine_id=m.id,
            machine_code=m.machine_code,
            type=m.type.value,
            line_id=m.line_id,
            sample_count=int(r.n) if r else 0,
            running_pct=running_pct,
            avg_rpm=round(avg_rpm, 0) if avg_rpm is not None else None,
            last_seen=last_seen,
            last_state="RUNNING" if latest_state.get(m.id) else "IDLE",
        ))
    return out
