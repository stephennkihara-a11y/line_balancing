"""Bottleneck dashboard: heatmap + WIP alerts + root-cause."""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..database import get_db
from ..models import (
    BalanceRun, BalanceAssignment, Operator, Operation,
    StationWIP, HourlyProduction, User,
)
from ..schemas.dashboard import (
    BottleneckDashboardResponse, StationHeatPoint, WIPAlert, HourlyProductionOut,
)
from ..services import root_cause as root_cause_service
from ..services.rebalance import _latest_run_for_line

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/bottleneck", response_model=BottleneckDashboardResponse)
def bottleneck(
    line_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BottleneckDashboardResponse:
    run = _latest_run_for_line(db, line_id)
    if not run:
        return BottleneckDashboardResponse(
            line_id=line_id, run_id=None, line_efficiency=None, balance_loss=None,
            target_output_hour=None, heat=[], bottleneck_station=None,
            bottleneck_op_code=None, wip_alerts=[], root_causes=[], last_hour=None,
        )

    # Build heat map
    assignments = (
        db.query(BalanceAssignment)
        .filter(BalanceAssignment.run_id == run.id)
        .order_by(BalanceAssignment.station)
        .all()
    )
    by_st: dict[int, list[BalanceAssignment]] = defaultdict(list)
    for a in assignments:
        by_st[a.station].append(a)
    cycles = {st: sum(float(a.cycle_time) for a in lst) for st, lst in by_st.items()}
    cycle_max = max(cycles.values(), default=0.0)
    bottleneck_station = max(cycles, key=cycles.get) if cycles else None
    bottleneck_op_code = None
    if run.bottleneck_op_id:
        op = db.get(Operation, run.bottleneck_op_id)
        if op:
            bottleneck_op_code = op.op_code

    # Latest WIP per station
    latest_wip_rows = (
        db.query(StationWIP)
        .filter(StationWIP.run_id == run.id)
        .order_by(StationWIP.station, desc(StationWIP.captured_at))
        .all()
    )
    seen: set[int] = set()
    latest_wip: dict[int, StationWIP] = {}
    for r in latest_wip_rows:
        if r.station not in seen:
            latest_wip[r.station] = r
            seen.add(r.station)

    heat: list[StationHeatPoint] = []
    for st in sorted(by_st.keys()):
        items = by_st[st]
        opr = db.get(Operator, items[0].operator_id) if items[0].operator_id else None
        ops = [db.get(Operation, a.operation_id) for a in items]
        wip = latest_wip.get(st)
        heat.append(StationHeatPoint(
            station=st,
            operator_name=opr.name if opr else None,
            op_codes=[o.op_code for o in ops if o],
            machine_type=ops[0].machine_type.value if ops and ops[0] else "",
            cycle_time=round(cycles[st], 3),
            load_pct=round((cycles[st] / cycle_max * 100) if cycle_max else 0, 2),
            is_bottleneck=(st == bottleneck_station),
            wip_units=wip.wip_units if wip else None,
            wip_threshold=wip.threshold if wip else None,
        ))

    # WIP alerts
    alerts: list[WIPAlert] = []
    for st, w in latest_wip.items():
        if w.wip_units >= w.threshold:
            alerts.append(WIPAlert(
                run_id=run.id, station=st, wip_units=w.wip_units, threshold=w.threshold,
                severity="critical" if w.wip_units >= w.threshold * 1.5 else "warning",
            ))

    # Last hour
    last_hour = (
        db.query(HourlyProduction)
        .filter(HourlyProduction.line_id == line_id)
        .order_by(desc(HourlyProduction.captured_at))
        .first()
    )

    return BottleneckDashboardResponse(
        line_id=line_id,
        run_id=run.id,
        line_efficiency=float(run.line_efficiency or 0),
        balance_loss=float(run.balance_loss or 0),
        target_output_hour=run.target_output_hour,
        heat=heat,
        bottleneck_station=bottleneck_station,
        bottleneck_op_code=bottleneck_op_code,
        wip_alerts=alerts,
        root_causes=root_cause_service.analyse(db, run),
        last_hour=HourlyProductionOut.model_validate(last_hour) if last_hour else None,
    )
