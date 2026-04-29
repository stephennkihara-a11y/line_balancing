"""Heuristic root-cause analysis for the bottleneck station of a run.

Returns a list of (cause, detail, suggestion) triples sorted by likelihood.
The rules are deliberately simple so they're explainable on the floor:

  * skill_gap   — operator at the bottleneck has below-average efficiency on
                  this op vs other certified operators
  * machine     — machine of the required type is in BREAKDOWN, or pool is
                  exhausted
  * method      — captured time-study SAM is materially higher than the
                  standard SAM on the bottleneck op
  * layout      — multiple ops at the station whose combined SAM exceeds the
                  takt (genuinely overloaded — split the station)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    BalanceRun, BalanceAssignment, Operator, OperatorSkill, Operation,
    Machine, MachineStatus, TimeStudy,
)
from ..schemas.dashboard import BottleneckRootCause


def analyse(db: Session, run: BalanceRun) -> list[BottleneckRootCause]:
    if not run.bottleneck_op_id:
        return []

    assignments = (
        db.query(BalanceAssignment)
        .filter(BalanceAssignment.run_id == run.id)
        .all()
    )
    if not assignments:
        return []

    # Find the bottleneck station = max station load
    by_station: dict[int, list[BalanceAssignment]] = defaultdict(list)
    for a in assignments:
        by_station[a.station].append(a)
    cycles = {st: sum(float(a.cycle_time) for a in lst) for st, lst in by_station.items()}
    bottleneck_station = max(cycles, key=cycles.get)
    items = by_station[bottleneck_station]
    bottleneck_op = db.get(Operation, run.bottleneck_op_id)
    bottleneck_assign = next(
        (a for a in items if a.operation_id == run.bottleneck_op_id),
        items[0],  # fallback
    )

    causes: list[BottleneckRootCause] = []

    # ---------- skill_gap ----------
    if bottleneck_assign.operator_id and bottleneck_op:
        my_skill = (
            db.query(OperatorSkill)
            .filter(
                OperatorSkill.operator_id == bottleneck_assign.operator_id,
                OperatorSkill.operation_id == bottleneck_op.id,
            )
            .first()
        )
        avg_eff = (
            db.query(func.avg(OperatorSkill.efficiency))
            .filter(OperatorSkill.operation_id == bottleneck_op.id)
            .scalar()
        )
        if my_skill and avg_eff:
            mine = float(my_skill.efficiency)
            avg = float(avg_eff)
            if mine < avg - 8:                        # >8 pts below mean
                operator = db.get(Operator, bottleneck_assign.operator_id)
                # Find a faster certified operator
                faster = (
                    db.query(Operator)
                    .join(OperatorSkill, OperatorSkill.operator_id == Operator.id)
                    .filter(OperatorSkill.operation_id == bottleneck_op.id)
                    .filter(OperatorSkill.efficiency >= avg + 5)
                    .order_by(OperatorSkill.efficiency.desc())
                    .first()
                )
                detail = (
                    f"{operator.name if operator else 'operator'} runs op "
                    f"{bottleneck_op.op_code} at {mine:.0f}% efficiency vs an "
                    f"average of {avg:.0f}%."
                )
                suggestion = (
                    f"Swap with {faster.name} (faster on this op) "
                    if faster else
                    "Cross-train another operator on this op or split it."
                )
                causes.append(BottleneckRootCause(
                    cause="skill_gap", detail=detail, suggestion=suggestion,
                ))

    # ---------- machine ----------
    if bottleneck_op:
        broken = (
            db.query(func.count(Machine.id))
            .filter(Machine.type == bottleneck_op.machine_type)
            .filter(Machine.status == MachineStatus.BREAKDOWN)
            .scalar()
        ) or 0
        total = (
            db.query(func.count(Machine.id))
            .filter(Machine.type == bottleneck_op.machine_type)
            .scalar()
        ) or 0
        if broken > 0:
            causes.append(BottleneckRootCause(
                cause="machine",
                detail=f"{broken}/{total} {bottleneck_op.machine_type.value} machines in BREAKDOWN.",
                suggestion="Recover broken machines or relocate the operation to a parallel station.",
            ))

    # ---------- method (time study vs standard) ----------
    if bottleneck_op:
        ts_avg = (
            db.query(func.avg(TimeStudy.captured_sam))
            .filter(TimeStudy.operation_id == bottleneck_op.id)
            .scalar()
        )
        if ts_avg:
            ts_avg = float(ts_avg)
            standard = float(bottleneck_op.sam)
            if ts_avg > standard * 1.10:              # 10% over standard
                causes.append(BottleneckRootCause(
                    cause="method",
                    detail=(
                        f"Captured SAM averages {ts_avg:.3f} min vs standard "
                        f"{standard:.3f} min ({(ts_avg/standard - 1)*100:+.1f}%)."
                    ),
                    suggestion=(
                        "Re-do the method study on this op — likely a workplace "
                        "layout, attachment or motion-economy issue."
                    ),
                ))

    # ---------- layout (overloaded station) ----------
    total_sam_at_station = sum(float(db.get(Operation, a.operation_id).sam) for a in items)
    takt = float(run.takt_time or 0)
    if takt > 0 and total_sam_at_station > takt * 1.10:
        causes.append(BottleneckRootCause(
            cause="layout",
            detail=(
                f"Station {bottleneck_station} carries {total_sam_at_station:.3f} min of "
                f"work vs takt {takt:.3f} min."
            ),
            suggestion=(
                "Split the station: move one of "
                f"{', '.join(db.get(Operation, a.operation_id).op_code for a in items[:3])} "
                "to a new station."
            ),
        ))

    return causes
