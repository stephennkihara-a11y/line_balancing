from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    Style, Operation, OperationPrecedence,
    Operator, OperatorSkill, AttendanceStatus,
    Line, Machine, MachineStatus, MachineType,
    BalanceRun, BalanceAssignment, BalanceStatus,
    User, UserRole,
)
from ..schemas.balance import (
    BalanceRequest, BalanceResponse, AssignmentOut, StationLoad,
    BalanceRunOut, ExplainRequest, ExplainResponse,
    BalanceSuggestionRequest, BalanceSuggestionResponse,
)
from ..auth.security import require_role, get_current_user
from ..config import get_settings
from ..services.solver import (
    SolverInput, OpDTO, OperatorDTO, solve, compute_takt,
)
from ..services import claude_advisor
from ..services.suggestion import SuggestionInput, suggest as _suggest_calc

router = APIRouter(prefix="/api/balance", tags=["balance"])


def _build_solver_input(
    db: Session, req: BalanceRequest,
) -> tuple[SolverInput, dict[int, Operation], dict[int, Operator], dict[str, list[Machine]]]:
    style = db.query(Style).options(selectinload(Style.operations)).filter(Style.id == req.style_id).first()
    if not style:
        raise HTTPException(404, "Style not found")
    line = db.get(Line, req.line_id)
    if not line:
        raise HTTPException(404, "Line not found")
    if not style.operations:
        raise HTTPException(400, "Style has no operations")

    # Operators
    op_q = db.query(Operator).options(selectinload(Operator.skills)).filter(Operator.is_active.is_(True))
    if req.available_operator_ids:
        op_q = op_q.filter(Operator.id.in_(req.available_operator_ids))
    else:
        op_q = op_q.filter(
            Operator.attendance_status == AttendanceStatus.PRESENT,
            (Operator.current_line_id == req.line_id) | (Operator.current_line_id.is_(None)),
        )
    operators = op_q.all()
    if not operators:
        raise HTTPException(400, "No operators available")

    # Machines on line (or unassigned)
    machines = (
        db.query(Machine)
        .filter(
            Machine.status.in_([MachineStatus.WORKING, MachineStatus.IDLE]),
            (Machine.line_id == req.line_id) | (Machine.line_id.is_(None)),
        )
        .all()
    )
    machines_by_type: dict[str, list[Machine]] = defaultdict(list)
    for m in machines:
        machines_by_type[m.type.value].append(m)
    machines_available = {t: len(ms) for t, ms in machines_by_type.items()}

    # Build dense indices
    op_dtos: list[OpDTO] = []
    op_id_to_idx: dict[int, int] = {}
    op_by_idx: dict[int, Operation] = {}
    for i, op in enumerate(style.operations):
        op_dtos.append(OpDTO(
            idx=i, op_id=op.id, op_code=op.op_code, sam=float(op.sam),
            machine_type=op.machine_type.value, skill_level=op.skill_level,
        ))
        op_id_to_idx[op.id] = i
        op_by_idx[i] = op

    operator_dtos: list[OperatorDTO] = []
    operator_id_to_idx: dict[int, int] = {}
    operator_by_idx: dict[int, Operator] = {}
    for i, opr in enumerate(operators):
        operator_dtos.append(OperatorDTO(
            idx=i, operator_id=opr.id, name=opr.name, base_efficiency=float(opr.base_efficiency),
        ))
        operator_id_to_idx[opr.id] = i
        operator_by_idx[i] = opr

    # Precedence
    precs = db.query(OperationPrecedence).filter(OperationPrecedence.style_id == style.id).all()
    precedence = [
        (op_id_to_idx[p.predecessor_id], op_id_to_idx[p.successor_id])
        for p in precs
        if p.predecessor_id in op_id_to_idx and p.successor_id in op_id_to_idx
    ]

    # Skill matrix
    skill_matrix: dict[tuple[int, int], float] = {}
    for opr in operators:
        for sk in opr.skills:
            if sk.operation_id in op_id_to_idx and sk.is_certified:
                skill_matrix[(operator_id_to_idx[opr.id], op_id_to_idx[sk.operation_id])] = float(sk.efficiency)

    settings = get_settings()
    sin = SolverInput(
        operations=op_dtos,
        operators=operator_dtos,
        precedence=precedence,
        skill_matrix=skill_matrix,
        machines_available=machines_available,
        target_output_hour=req.target_output_hour,
        working_minutes=req.working_minutes,
        time_limit_s=req.solver_time_limit_s or settings.solver_time_limit_s,
    )
    return sin, op_by_idx, operator_by_idx, machines_by_type


@router.post("/run", response_model=BalanceResponse)
def run_balance(
    payload: BalanceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> BalanceResponse:
    sin, op_by_idx, operator_by_idx, machines_by_type = _build_solver_input(db, payload)
    result = solve(sin)

    # Persist run
    run = BalanceRun(
        style_id=payload.style_id,
        line_id=payload.line_id,
        target_output_hour=payload.target_output_hour,
        working_minutes=payload.working_minutes,
        available_operators=len(sin.operators),
        takt_time=result.takt_time,
        theoretical_ops=result.theoretical_ops,
        line_efficiency=result.line_efficiency,
        balance_loss=result.balance_loss,
        status=BalanceStatus.PROPOSED if result.assignments else BalanceStatus.DRAFT,
        solver="cp-sat",
        created_by=user.id,
    )
    db.add(run)
    db.flush()

    # Build assignments and station loads
    assignments_out: list[AssignmentOut] = []
    station_to_ops: dict[int, list] = defaultdict(list)
    used_machines: dict[str, list[int]] = defaultdict(list)  # type -> available machine ids pool

    for mtype, ms in machines_by_type.items():
        used_machines[mtype] = [m.id for m in ms]

    for a in result.assignments:
        op = op_by_idx[a.op_idx]
        opr = operator_by_idx.get(a.operator_idx) if a.operator_idx >= 0 else None
        # Pick a machine of matching type if any
        machine_id = None
        pool = used_machines.get(op.machine_type.value, [])
        # Each station with that op uses one machine slot
        if pool and not any(
            asg.machine_id and asg.station == a.station and asg.operation.machine_type == op.machine_type
            for asg in []  # intentionally empty; assigned below
        ):
            machine_id = pool.pop(0) if pool else None
        ba = BalanceAssignment(
            run_id=run.id,
            station=a.station,
            operator_id=opr.id if opr else None,
            operation_id=op.id,
            machine_id=machine_id,
            cycle_time=a.cycle_time,
            expected_output=int(60.0 / a.cycle_time) if a.cycle_time > 0 else None,
        )
        db.add(ba)
        station_to_ops[a.station].append((op, opr, a.cycle_time, machine_id))

        assignments_out.append(AssignmentOut(
            station=a.station,
            operator_id=opr.id if opr else None,
            operator_name=opr.name if opr else None,
            operation_id=op.id,
            operation_code=op.op_code,
            operation_description=op.description,
            machine_id=machine_id,
            machine_type=op.machine_type.value,
            sam=float(op.sam),
            cycle_time=a.cycle_time,
            expected_output=int(60.0 / a.cycle_time) if a.cycle_time > 0 else None,
        ))

    # Set bottleneck operation id (from station with max load)
    bottleneck_op_code = None
    bottleneck_station = result.bottleneck_station
    if bottleneck_station and bottleneck_station in station_to_ops:
        ops_at_b = station_to_ops[bottleneck_station]
        # heaviest individual op in that station
        heaviest = max(ops_at_b, key=lambda t: t[2])
        run.bottleneck_op_id = heaviest[0].id
        bottleneck_op_code = heaviest[0].op_code

    # Build station loads (cycle_time = sum at station)
    cycle_time = max(result.station_cycle_min) if result.station_cycle_min else 0.0
    station_loads: list[StationLoad] = []
    for st in sorted(station_to_ops.keys()):
        ops_here = station_to_ops[st]
        load = sum(t[2] for t in ops_here)
        first_op = ops_here[0][0]
        opr = ops_here[0][1]
        station_loads.append(StationLoad(
            station=st,
            operator_id=opr.id if opr else None,
            operator_name=opr.name if opr else None,
            operation_ids=[t[0].id for t in ops_here],
            operation_codes=[t[0].op_code for t in ops_here],
            machine_type=first_op.machine_type.value,
            cycle_time=round(load, 3),
            load_pct=round((load / cycle_time * 100.0) if cycle_time > 0 else 0.0, 2),
            is_bottleneck=(st == bottleneck_station),
        ))

    explanation = None
    if payload.explain and result.assignments:
        summary = _summary_for_claude(run, op_by_idx, station_loads, bottleneck_op_code, result.warnings, db)
        explanation = claude_advisor.explain_balance(summary)
        run.explanation = explanation

    db.commit()

    return BalanceResponse(
        run_id=run.id,
        style_id=payload.style_id,
        line_id=payload.line_id,
        takt_time=round(result.takt_time, 4),
        theoretical_ops=result.theoretical_ops,
        line_efficiency=result.line_efficiency,
        balance_loss=result.balance_loss,
        bottleneck_station=bottleneck_station,
        bottleneck_operation_code=bottleneck_op_code,
        status=run.status,
        solver=run.solver,
        solver_status=result.status,
        assignments=sorted(assignments_out, key=lambda a: (a.station, a.operation_code)),
        station_loads=station_loads,
        explanation=explanation,
        warnings=result.warnings,
    )


def _summary_for_claude(
    run: BalanceRun,
    op_by_idx: dict,
    station_loads: list[StationLoad],
    bottleneck_op_code: str | None,
    warnings: list[str],
    db: Session,
) -> dict:
    style = db.get(Style, run.style_id)
    line = db.get(Line, run.line_id)
    cycle = max((s.cycle_time for s in station_loads), default=0.0)
    return {
        "style_code": style.style_code,
        "style_name": style.name,
        "line_code": line.code,
        "target_output_hour": run.target_output_hour,
        "working_minutes": run.working_minutes,
        "takt_time": float(run.takt_time or 0),
        "theoretical_ops": run.theoretical_ops,
        "stations_used": len(station_loads),
        "line_efficiency": float(run.line_efficiency or 0),
        "balance_loss": float(run.balance_loss or 0),
        "bottleneck_station": run.bottleneck_op_id and next(
            (s.station for s in station_loads if s.is_bottleneck), None
        ),
        "bottleneck_op_code": bottleneck_op_code,
        "bottleneck_cycle_min": cycle,
        "station_summary": [
            {
                "station": s.station,
                "operator_name": s.operator_name or "(unassigned)",
                "op_codes": s.operation_codes,
                "machine_type": s.machine_type,
                "cycle_time": s.cycle_time,
                "load_pct": s.load_pct,
            }
            for s in station_loads
        ],
        "warnings": warnings,
    }


@router.get("/runs", response_model=list[BalanceRunOut])
def list_runs(
    style_id: int | None = None, line_id: int | None = None,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[BalanceRun]:
    q = db.query(BalanceRun)
    if style_id:
        q = q.filter(BalanceRun.style_id == style_id)
    if line_id:
        q = q.filter(BalanceRun.line_id == line_id)
    return q.order_by(BalanceRun.created_at.desc()).limit(100).all()


@router.get("/runs/{run_id}", response_model=BalanceResponse)
def get_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> BalanceResponse:
    run = (
        db.query(BalanceRun)
        .options(selectinload(BalanceRun.assignments))
        .filter(BalanceRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")

    # Reconstruct response from persisted data
    station_to_ops: dict[int, list[BalanceAssignment]] = defaultdict(list)
    for a in run.assignments:
        station_to_ops[a.station].append(a)

    cycle_time = max(
        (sum(float(a.cycle_time) for a in lst) for lst in station_to_ops.values()),
        default=0.0,
    )

    bottleneck_station = None
    if station_to_ops:
        bottleneck_station = max(
            station_to_ops.keys(),
            key=lambda st: sum(float(a.cycle_time) for a in station_to_ops[st]),
        )

    bottleneck_op_code = None
    if run.bottleneck_op_id:
        op = db.get(Operation, run.bottleneck_op_id)
        if op:
            bottleneck_op_code = op.op_code

    assignments_out: list[AssignmentOut] = []
    station_loads: list[StationLoad] = []
    for st in sorted(station_to_ops.keys()):
        items = station_to_ops[st]
        load = sum(float(a.cycle_time) for a in items)
        first = items[0]
        op_codes = []
        op_ids = []
        for a in items:
            op = db.get(Operation, a.operation_id)
            opr_obj = db.get(Operator, a.operator_id) if a.operator_id else None
            assignments_out.append(AssignmentOut(
                station=a.station,
                operator_id=a.operator_id,
                operator_name=opr_obj.name if opr_obj else None,
                operation_id=a.operation_id,
                operation_code=op.op_code if op else "",
                operation_description=op.description if op else "",
                machine_id=a.machine_id,
                machine_type=op.machine_type.value if op else "",
                sam=float(op.sam) if op else 0.0,
                cycle_time=float(a.cycle_time),
                expected_output=a.expected_output,
            ))
            op_codes.append(op.op_code if op else "")
            op_ids.append(a.operation_id)
        first_op = db.get(Operation, first.operation_id)
        first_opr = db.get(Operator, first.operator_id) if first.operator_id else None
        station_loads.append(StationLoad(
            station=st,
            operator_id=first.operator_id,
            operator_name=first_opr.name if first_opr else None,
            operation_ids=op_ids,
            operation_codes=op_codes,
            machine_type=first_op.machine_type.value if first_op else "",
            cycle_time=round(load, 3),
            load_pct=round(load / cycle_time * 100.0 if cycle_time else 0, 2),
            is_bottleneck=(st == bottleneck_station),
        ))

    return BalanceResponse(
        run_id=run.id,
        style_id=run.style_id,
        line_id=run.line_id,
        takt_time=float(run.takt_time or 0),
        theoretical_ops=run.theoretical_ops or 0,
        line_efficiency=float(run.line_efficiency or 0),
        balance_loss=float(run.balance_loss or 0),
        bottleneck_station=bottleneck_station,
        bottleneck_operation_code=bottleneck_op_code,
        status=run.status,
        solver=run.solver,
        solver_status="STORED",
        assignments=sorted(assignments_out, key=lambda a: (a.station, a.operation_code)),
        station_loads=station_loads,
        explanation=run.explanation,
        warnings=[],
    )


@router.post("/runs/{run_id}/explain", response_model=ExplainResponse)
def explain_run(
    run_id: int, payload: ExplainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExplainResponse:
    resp = get_run(run_id, db, user)
    summary = {
        "style_code": db.get(Style, resp.style_id).style_code,
        "style_name": db.get(Style, resp.style_id).name,
        "line_code": db.get(Line, resp.line_id).code,
        "target_output_hour": db.get(BalanceRun, run_id).target_output_hour,
        "working_minutes": db.get(BalanceRun, run_id).working_minutes,
        "takt_time": resp.takt_time,
        "theoretical_ops": resp.theoretical_ops,
        "stations_used": len(resp.station_loads),
        "line_efficiency": resp.line_efficiency,
        "balance_loss": resp.balance_loss,
        "bottleneck_station": resp.bottleneck_station,
        "bottleneck_op_code": resp.bottleneck_operation_code,
        "bottleneck_cycle_min": max((s.cycle_time for s in resp.station_loads), default=0.0),
        "station_summary": [
            {
                "station": s.station,
                "operator_name": s.operator_name or "(unassigned)",
                "op_codes": s.operation_codes,
                "machine_type": s.machine_type,
                "cycle_time": s.cycle_time,
                "load_pct": s.load_pct,
            }
            for s in resp.station_loads
        ],
        "warnings": resp.warnings,
    }
    text = claude_advisor.explain_balance(summary, payload.question)
    run = db.get(BalanceRun, run_id)
    run.explanation = text
    db.commit()
    return ExplainResponse(run_id=run_id, explanation=text)


@router.post("/runs/{run_id}/apply", response_model=BalanceRunOut)
def apply_run(
    run_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.SUPERVISOR)),
) -> BalanceRun:
    run = db.get(BalanceRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    run.status = BalanceStatus.APPLIED
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------
# Pre-balance suggestion: "what target output should we aim for?"
# ---------------------------------------------------------------------
@router.post("/suggest", response_model=BalanceSuggestionResponse)
def suggest_target(
    payload: BalanceSuggestionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BalanceSuggestionResponse:
    """Compute suggested hourly output for a (style, line, operators, eff) tuple.

    Defaults `operators` to the line's planned capacity. The math:
        output/hr = (operators × 60 × efficiency) / total_SAM
    plus a hard cap from the heaviest single operation, plus a reverse
    "operators required to hit X/hr" calculation when target_output_hour
    is supplied.
    """
    style = (
        db.query(Style)
        .options(selectinload(Style.operations))
        .filter(Style.id == payload.style_id)
        .first()
    )
    if not style:
        raise HTTPException(404, "Style not found")
    if not style.operations:
        raise HTTPException(400, "Style has no operations")

    line = db.get(Line, payload.line_id)
    if not line:
        raise HTTPException(404, "Line not found")

    operators = payload.operators or line.capacity
    total_sam = sum(float(o.sam) for o in style.operations)

    heaviest_op = max(style.operations, key=lambda o: float(o.sam))
    bottleneck_min = float(heaviest_op.sam)
    bottleneck_code = heaviest_op.op_code

    res = _suggest_calc(SuggestionInput(
        total_sam_min=total_sam,
        operators=operators,
        efficiency_pct=payload.efficiency_pct,
        working_minutes=payload.working_minutes,
        target_output_hour=payload.target_output_hour,
        bottleneck_op_min=bottleneck_min,
        bottleneck_op_code=bottleneck_code,
    ))

    return BalanceSuggestionResponse(
        style_id=style.id,
        line_id=line.id,
        total_sam_min=round(total_sam, 3),
        operators_used=operators,
        efficiency_pct=payload.efficiency_pct,
        working_minutes=payload.working_minutes,
        suggested_output_hour=res.suggested_output_hour,
        suggested_output_day=res.suggested_output_day,
        takt_time_min=res.takt_time_min,
        theoretical_operators_at_target=res.theoretical_operators_at_target,
        bottleneck_op_min=round(bottleneck_min, 3),
        bottleneck_op_code=bottleneck_code,
        notes=res.notes,
    )
