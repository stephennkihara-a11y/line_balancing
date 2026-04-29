"""Hourly production capture + WIP tracking."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..auth.security import get_current_user, require_role
from ..database import get_db
from ..models import (
    HourlyProduction, StationWIP, BalanceRun, User, UserRole,
)
from ..schemas.dashboard import (
    HourlyProductionCreate, HourlyProductionOut,
    StationWIPCreate, StationWIPOut,
)

router = APIRouter(prefix="/api/production", tags=["production"])


# ---------- hourly production ---------------------------------------
@router.post("/hourly", response_model=HourlyProductionOut, status_code=201)
def post_hourly(
    payload: HourlyProductionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.SUPERVISOR, UserRole.IE, UserRole.PRODUCTION_MANAGER)),
) -> HourlyProduction:
    if payload.run_id and not db.get(BalanceRun, payload.run_id):
        raise HTTPException(404, "Run not found")
    rec = HourlyProduction(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/hourly", response_model=list[HourlyProductionOut])
def list_hourly(
    line_id: int, limit: int = 24,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[HourlyProduction]:
    return (
        db.query(HourlyProduction)
        .filter(HourlyProduction.line_id == line_id)
        .order_by(desc(HourlyProduction.captured_at))
        .limit(min(limit, 200))
        .all()
    )


# ---------- WIP -----------------------------------------------------
@router.post("/wip", response_model=StationWIPOut, status_code=201)
def post_wip(
    payload: StationWIPCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.SUPERVISOR, UserRole.IE, UserRole.PRODUCTION_MANAGER)),
) -> StationWIP:
    if not db.get(BalanceRun, payload.run_id):
        raise HTTPException(404, "Run not found")
    rec = StationWIP(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/wip", response_model=list[StationWIPOut])
def list_wip(
    run_id: int,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> list[StationWIP]:
    """Return latest WIP entry per station for a run."""
    rows = (
        db.query(StationWIP)
        .filter(StationWIP.run_id == run_id)
        .order_by(StationWIP.station, desc(StationWIP.captured_at))
        .all()
    )
    seen: set[int] = set()
    out: list[StationWIP] = []
    for r in rows:
        if r.station in seen:
            continue
        seen.add(r.station)
        out.append(r)
    return out
