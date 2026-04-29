"""Real-time re-balance routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.security import get_current_user, require_role
from ..database import get_db
from ..models import (
    BalanceRun, BalanceStatus, Line, RebalanceEvent, RebalanceTrigger,
    User, UserRole,
)
from ..schemas.balance import BalanceRequest, BalanceResponse
from ..schemas.dashboard import (
    RebalanceCheckResponse, RebalanceProposeRequest, RebalanceDiffResponse,
    RebalanceAcceptRequest,
)
from ..services import rebalance as rb
from ..routers.balance import run_balance, get_run

router = APIRouter(prefix="/api/rebalance", tags=["rebalance"])


@router.get("/check", response_model=RebalanceCheckResponse)
def check(
    line_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RebalanceCheckResponse:
    if not db.get(Line, line_id):
        raise HTTPException(404, "Line not found")
    return rb.check_triggers(db, line_id)


@router.post("/propose", response_model=RebalanceDiffResponse)
def propose(
    payload: RebalanceProposeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.IE, UserRole.SUPERVISOR)),
) -> RebalanceDiffResponse:
    line = db.get(Line, payload.line_id)
    if not line:
        raise HTTPException(404, "Line not found")

    prev_run = rb._latest_run_for_line(db, payload.line_id)
    if not prev_run:
        raise HTTPException(400, "No previous run for line — start with /balance/run first")

    target = payload.target_output_hour or prev_run.target_output_hour

    # Re-solve using current PRESENT operators + WORKING/IDLE machines
    solver_resp: BalanceResponse = run_balance(
        BalanceRequest(
            style_id=prev_run.style_id,
            line_id=payload.line_id,
            target_output_hour=target,
            working_minutes=prev_run.working_minutes,
            available_operator_ids=None,    # use current attendance
            explain=payload.explain,
        ),
        db, user,
    )
    new_run = db.get(BalanceRun, solver_resp.run_id)

    # Diff against previous applied/proposed run
    diffs, eff_before, eff_after, output_before, output_after = rb.diff_runs(db, prev_run, new_run)

    detail = {
        "trigger": payload.trigger.value,
        "target": target,
        "warnings": solver_resp.warnings,
    }
    event = rb.record_event(
        db, line_id=payload.line_id, prev_run=prev_run, new_run=new_run,
        trigger=payload.trigger, detail=detail,
        eff_before=eff_before, eff_after=eff_after,
        output_before=output_before, output_after=output_after,
        user_id=user.id,
    )
    db.commit()

    return RebalanceDiffResponse(
        event_id=event.id,
        previous_run_id=prev_run.id,
        new_run_id=new_run.id,
        trigger=payload.trigger,
        eff_before=eff_before,
        eff_after=eff_after,
        output_before=output_before,
        output_after=output_after,
        delta_eff=round((eff_after or 0) - (eff_before or 0), 2),
        delta_output=(output_after or 0) - (output_before or 0),
        diffs=diffs,
        explanation=solver_resp.explanation,
        warnings=solver_resp.warnings,
    )


@router.post("/events/{event_id}/decide", response_model=RebalanceDiffResponse)
def decide(
    event_id: int, payload: RebalanceAcceptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PRODUCTION_MANAGER, UserRole.SUPERVISOR)),
) -> RebalanceDiffResponse:
    ev = db.get(RebalanceEvent, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    ev.accepted = payload.accepted

    # If accepted, mark new run APPLIED and demote the previous run
    if payload.accepted and ev.new_run_id:
        prev = db.get(BalanceRun, ev.previous_run_id) if ev.previous_run_id else None
        new = db.get(BalanceRun, ev.new_run_id)
        if new:
            new.status = BalanceStatus.APPLIED
        if prev:
            prev.status = BalanceStatus.REJECTED
    db.commit()

    prev_run = db.get(BalanceRun, ev.previous_run_id) if ev.previous_run_id else None
    new_run = db.get(BalanceRun, ev.new_run_id)
    diffs, eff_before, eff_after, output_before, output_after = rb.diff_runs(db, prev_run, new_run) if new_run else ([], None, 0, None, 0)
    return RebalanceDiffResponse(
        event_id=ev.id,
        previous_run_id=ev.previous_run_id,
        new_run_id=ev.new_run_id or 0,
        trigger=ev.trigger,
        eff_before=float(ev.eff_before) if ev.eff_before is not None else None,
        eff_after=float(ev.eff_after or 0),
        output_before=ev.output_before,
        output_after=ev.output_after or 0,
        delta_eff=round(float(ev.eff_after or 0) - float(ev.eff_before or 0), 2),
        delta_output=(ev.output_after or 0) - (ev.output_before or 0),
        diffs=diffs,
        explanation=None,
        warnings=[],
    )


@router.get("/events", response_model=list[dict])
def list_events(
    line_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    q = db.query(RebalanceEvent).order_by(RebalanceEvent.created_at.desc())
    if line_id:
        q = q.filter(RebalanceEvent.line_id == line_id)
    rows = q.limit(min(limit, 200)).all()
    return [
        {
            "id": r.id,
            "line_id": r.line_id,
            "trigger": r.trigger.value,
            "previous_run_id": r.previous_run_id,
            "new_run_id": r.new_run_id,
            "eff_before": float(r.eff_before) if r.eff_before is not None else None,
            "eff_after": float(r.eff_after) if r.eff_after is not None else None,
            "delta_output": (r.output_after or 0) - (r.output_before or 0),
            "accepted": r.accepted,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
