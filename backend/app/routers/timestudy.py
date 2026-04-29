"""Time study capture + comparison vs standard SAM."""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..auth.security import get_current_user, require_role
from ..database import get_db
from ..models import Operation, Operator, TimeStudy, User, UserRole
from ..schemas.timestudy import TimeStudyCreate, TimeStudyOut, TimeStudyAggregate

router = APIRouter(prefix="/api/time-studies", tags=["time-study"])


def _to_out(ts: TimeStudy, op: Operation | None) -> TimeStudyOut:
    captured = float(ts.captured_sam) if ts.captured_sam is not None else None
    standard = float(op.sam) if op else None
    deviation = None
    if captured is not None and standard:
        deviation = round((captured / standard - 1) * 100, 2)
    return TimeStudyOut(
        id=ts.id,
        operation_id=ts.operation_id,
        operator_id=ts.operator_id,
        cycle_seconds=float(ts.cycle_seconds),
        rating=float(ts.rating),
        allowance=float(ts.allowance),
        captured_sam=captured,
        sample_size=ts.sample_size,
        note=ts.note,
        captured_at=ts.captured_at,
        operation_code=op.op_code if op else None,
        operation_description=op.description if op else None,
        standard_sam=standard,
        deviation_pct=deviation,
    )


@router.post("", response_model=TimeStudyOut, status_code=201)
def capture(
    payload: TimeStudyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.IE, UserRole.SUPERVISOR, UserRole.PRODUCTION_MANAGER)),
) -> TimeStudyOut:
    op = db.get(Operation, payload.operation_id)
    if not op:
        raise HTTPException(404, "Operation not found")
    if payload.operator_id and not db.get(Operator, payload.operator_id):
        raise HTTPException(404, "Operator not found")

    ts = TimeStudy(
        operation_id=payload.operation_id,
        operator_id=payload.operator_id,
        captured_by=user.id,
        cycle_seconds=payload.cycle_seconds,
        rating=payload.rating,
        allowance=payload.allowance,
        sample_size=payload.sample_size,
        note=payload.note,
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    # captured_sam is a generated column. SQLAlchemy may not have re-fetched it; compute fallback:
    if ts.captured_sam is None:
        ts.captured_sam = (
            (float(ts.cycle_seconds) / 60.0)
            * (float(ts.rating) / 100.0)
            * (1 + float(ts.allowance) / 100.0)
        )
    return _to_out(ts, op)


@router.get("", response_model=list[TimeStudyOut])
def list_studies(
    operation_id: int | None = None, operator_id: int | None = None, limit: int = 100,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[TimeStudyOut]:
    q = db.query(TimeStudy)
    if operation_id:
        q = q.filter(TimeStudy.operation_id == operation_id)
    if operator_id:
        q = q.filter(TimeStudy.operator_id == operator_id)
    rows = q.order_by(desc(TimeStudy.captured_at)).limit(min(limit, 500)).all()
    op_ids = {r.operation_id for r in rows}
    ops = {o.id: o for o in db.query(Operation).filter(Operation.id.in_(op_ids)).all()}
    return [_to_out(r, ops.get(r.operation_id)) for r in rows]


@router.get("/aggregate", response_model=list[TimeStudyAggregate])
def aggregate(
    style_id: int,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[TimeStudyAggregate]:
    """Per-operation captured-vs-standard SAM aggregate, flagged if deviating ±10%."""
    ops = db.query(Operation).filter(Operation.style_id == style_id).all()
    if not ops:
        return []
    op_ids = [o.id for o in ops]
    rows = (
        db.query(
            TimeStudy.operation_id,
            func.avg(TimeStudy.captured_sam).label("avg"),
            func.min(TimeStudy.captured_sam).label("mn"),
            func.max(TimeStudy.captured_sam).label("mx"),
            func.count(TimeStudy.id).label("n"),
        )
        .filter(TimeStudy.operation_id.in_(op_ids))
        .group_by(TimeStudy.operation_id)
        .all()
    )
    by_op = {r.operation_id: r for r in rows}
    out: list[TimeStudyAggregate] = []
    for op in ops:
        r = by_op.get(op.id)
        if not r or r.n == 0:
            continue
        dev = (float(r.avg) / float(op.sam) - 1) * 100 if op.sam else 0.0
        flag = "ok"
        if dev >= 10:
            flag = "high"
        elif dev <= -10:
            flag = "low"
        out.append(TimeStudyAggregate(
            operation_id=op.id,
            operation_code=op.op_code,
            standard_sam=float(op.sam),
            captured_avg=round(float(r.avg), 3),
            captured_min=round(float(r.mn), 3),
            captured_max=round(float(r.mx), 3),
            sample_count=int(r.n),
            deviation_pct=round(dev, 2),
            flag=flag,
        ))
    return out
