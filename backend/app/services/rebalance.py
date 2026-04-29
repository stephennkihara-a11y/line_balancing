"""Real-time re-balance services.

Two halves:
  * `check_triggers(...)` — read-only inspection of current line state to
    decide whether a re-balance is warranted.
  * `propose(...)` — call the existing solver with the *current* operator
    and machine availability, persist a new BalanceRun, build a station-by-
    station diff against the previous run, and record a RebalanceEvent.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ..models import (
    BalanceRun, BalanceAssignment, BalanceStatus,
    HourlyProduction, RebalanceEvent, RebalanceTrigger,
    Operator, AttendanceStatus, Machine, MachineStatus, Operation, Style, Line,
)
from ..schemas.balance import BalanceRequest
from ..schemas.dashboard import (
    RebalanceCheckResponse, RebalanceDiffResponse, StationDiff,
)


DEVIATION_THRESHOLD = 0.15   # 15% deviation triggers re-balance


@dataclass
class StationSnapshot:
    station: int
    operator_id: int | None
    operator_name: str | None
    op_codes: list[str]
    cycle: float
    load_pct: float
    is_bottleneck: bool


def _latest_run_for_line(db: Session, line_id: int) -> BalanceRun | None:
    return (
        db.query(BalanceRun)
        .filter(BalanceRun.line_id == line_id)
        .filter(BalanceRun.status.in_([BalanceStatus.APPLIED, BalanceStatus.PROPOSED]))
        .order_by(desc(BalanceRun.created_at))
        .first()
    )


def _snapshot_run(db: Session, run: BalanceRun) -> tuple[list[StationSnapshot], float, int]:
    """Return per-station snapshot, max cycle (min), and expected output/hr."""
    assignments = (
        db.query(BalanceAssignment)
        .filter(BalanceAssignment.run_id == run.id)
        .order_by(BalanceAssignment.station)
        .all()
    )
    by_station: dict[int, list[BalanceAssignment]] = defaultdict(list)
    for a in assignments:
        by_station[a.station].append(a)

    cycles = {
        st: sum(float(a.cycle_time) for a in lst) for st, lst in by_station.items()
    }
    cycle_time = max(cycles.values(), default=0.0)
    bottleneck = max(cycles, key=cycles.get) if cycles else None

    snaps: list[StationSnapshot] = []
    for st in sorted(by_station.keys()):
        items = by_station[st]
        opr = db.get(Operator, items[0].operator_id) if items[0].operator_id else None
        ops = [db.get(Operation, a.operation_id) for a in items]
        snaps.append(StationSnapshot(
            station=st,
            operator_id=items[0].operator_id,
            operator_name=opr.name if opr else None,
            op_codes=[o.op_code for o in ops if o],
            cycle=round(cycles[st], 3),
            load_pct=round((cycles[st] / cycle_time * 100) if cycle_time else 0, 2),
            is_bottleneck=(st == bottleneck),
        ))

    output_per_hr = int(60.0 / cycle_time) if cycle_time > 0 else 0
    return snaps, cycle_time, output_per_hr


def check_triggers(db: Session, line_id: int) -> RebalanceCheckResponse:
    run = _latest_run_for_line(db, line_id)
    reasons: list[str] = []
    trigger: RebalanceTrigger | None = None

    # 1. Absent operators currently in the run
    absent_ids: list[int] = []
    if run:
        operator_ids = {a.operator_id for a in run.assignments if a.operator_id}
        absent = (
            db.query(Operator)
            .filter(Operator.id.in_(operator_ids))
            .filter(Operator.attendance_status != AttendanceStatus.PRESENT)
            .all()
        )
        absent_ids = [o.id for o in absent]
        if absent_ids:
            reasons.append(f"{len(absent_ids)} assigned operator(s) absent")
            trigger = trigger or RebalanceTrigger.OPERATOR_ABSENT

    # 2. Broken machines on this line
    broken = (
        db.query(Machine)
        .filter(Machine.line_id == line_id, Machine.status == MachineStatus.BREAKDOWN)
        .all()
    )
    broken_ids = [m.id for m in broken]
    if broken_ids:
        reasons.append(f"{len(broken_ids)} machine(s) in BREAKDOWN")
        trigger = trigger or RebalanceTrigger.MACHINE_BREAKDOWN

    # 3. Hourly output deviation > 15%
    last_hour = (
        db.query(HourlyProduction)
        .filter(HourlyProduction.line_id == line_id)
        .order_by(desc(HourlyProduction.captured_at))
        .first()
    )
    deviation_pct = None
    last_actual = None
    if last_hour and last_hour.target > 0:
        last_actual = last_hour.actual
        deviation_pct = (last_hour.target - last_hour.actual) / last_hour.target
        if abs(deviation_pct) > DEVIATION_THRESHOLD:
            reasons.append(
                f"Last hour actual {last_hour.actual} vs target {last_hour.target} "
                f"({deviation_pct*100:+.1f}%)"
            )
            trigger = trigger or RebalanceTrigger.OUTPUT_DEVIATION

    target_output = run.target_output_hour if run else 0
    return RebalanceCheckResponse(
        line_id=line_id,
        run_id=run.id if run else None,
        triggered=bool(trigger),
        trigger=trigger,
        reasons=reasons,
        target_output_hour=target_output,
        last_hour_actual=last_actual,
        deviation_pct=round(deviation_pct * 100, 2) if deviation_pct is not None else None,
        absent_operator_ids=absent_ids,
        broken_machine_ids=broken_ids,
    )


def diff_runs(
    db: Session, prev_run: BalanceRun | None, new_run: BalanceRun,
) -> tuple[list[StationDiff], float | None, float, int | None, int]:
    prev_snaps: list[StationSnapshot] = []
    eff_before: float | None = None
    output_before: int | None = None
    if prev_run:
        prev_snaps, prev_cycle, output_before = _snapshot_run(db, prev_run)
        eff_before = float(prev_run.line_efficiency or 0)

    new_snaps, _, output_after = _snapshot_run(db, new_run)
    eff_after = float(new_run.line_efficiency or 0)

    prev_by_st = {s.station: s for s in prev_snaps}
    new_by_st = {s.station: s for s in new_snaps}
    all_stations = sorted(set(prev_by_st) | set(new_by_st))

    diffs: list[StationDiff] = []
    for st in all_stations:
        a = prev_by_st.get(st)
        b = new_by_st.get(st)
        diffs.append(StationDiff(
            station=st,
            operator_before=a.operator_name if a else None,
            operator_after=b.operator_name if b else None,
            op_codes_before=a.op_codes if a else [],
            op_codes_after=b.op_codes if b else [],
            cycle_before=a.cycle if a else 0.0,
            cycle_after=b.cycle if b else 0.0,
            load_pct_before=a.load_pct if a else 0.0,
            load_pct_after=b.load_pct if b else 0.0,
            is_bottleneck_after=b.is_bottleneck if b else False,
        ))

    return diffs, eff_before, eff_after, output_before, output_after


def record_event(
    db: Session, *, line_id: int, prev_run: BalanceRun | None, new_run: BalanceRun,
    trigger: RebalanceTrigger, detail: dict, eff_before: float | None,
    eff_after: float, output_before: int | None, output_after: int,
    user_id,
) -> RebalanceEvent:
    ev = RebalanceEvent(
        line_id=line_id,
        previous_run_id=prev_run.id if prev_run else None,
        new_run_id=new_run.id,
        trigger=trigger,
        detail=detail,
        eff_before=eff_before,
        eff_after=eff_after,
        output_before=output_before,
        output_after=output_after,
        accepted=None,
        created_by=user_id,
    )
    db.add(ev)
    db.flush()
    return ev


def latest_applied_run(db: Session, line_id: int) -> BalanceRun | None:
    return (
        db.query(BalanceRun)
        .filter(BalanceRun.line_id == line_id, BalanceRun.status == BalanceStatus.APPLIED)
        .order_by(desc(BalanceRun.created_at))
        .first()
    )
