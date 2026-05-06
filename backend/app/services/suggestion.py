"""Pre-balance suggestion engine.

Given a style's total SAM, a line's planned operator count, and a target
"industrial garment efficiency" (typically 75–85%), compute the optimal
hourly output the line can be expected to produce.

Math
----
Let
    S    = total Standard Allowed Minutes per garment (sum of op SAMs)
    N    = number of operators on the line
    E    = target efficiency as a fraction (0.80 = 80%)

Each operator produces  E · 60 minutes of "earned SAM" per clock hour.
N operators together produce  N · E · 60 earned minutes per hour.
Throughput (pieces/hour) is the earned minutes divided by the SAM
content of one piece:

    output_per_hour = (N · E · 60) / S

Reverse: number of operators needed to hit a target output T:

    N_required(T) = ceil(T · S / (E · 60))

Hard floors
-----------
Two physical limits the user should be reminded of:

* The bottleneck operation. If the heaviest single op takes B minutes,
  the line cannot run faster than 60/B pieces per hour, no matter how
  many operators we add. A suggestion that ignores this is wishful.

* The theoretical-minimum-operator floor. With infinite efficiency you
  still need at least  ceil(S / takt)  operators.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass
class SuggestionInput:
    total_sam_min: float                    # sum of all operations' SAM (min)
    operators: int                          # planned operators on the line
    efficiency_pct: float                   # 80 means 80%
    working_minutes: int = 480              # minutes per shift
    target_output_hour: int | None = None
    bottleneck_op_min: float | None = None  # max single op SAM, optional
    bottleneck_op_code: str | None = None


@dataclass
class SuggestionResult:
    suggested_output_hour: int
    suggested_output_day: int
    takt_time_min: float
    theoretical_operators_at_target: int | None
    notes: list[str]


def suggest(inp: SuggestionInput) -> SuggestionResult:
    notes: list[str] = []

    if inp.total_sam_min <= 0:
        return SuggestionResult(
            suggested_output_hour=0,
            suggested_output_day=0,
            takt_time_min=0.0,
            theoretical_operators_at_target=None,
            notes=["Style has no operations — total SAM is zero."],
        )

    eff_frac = max(inp.efficiency_pct, 1) / 100.0
    earned_per_hour = inp.operators * 60.0 * eff_frac          # minutes
    raw = earned_per_hour / inp.total_sam_min                   # pieces/hr

    # Cap by the heaviest single operation: nothing flows through the
    # bottleneck faster than 60 / bottleneck_min.
    capped_by_bottleneck = False
    if inp.bottleneck_op_min and inp.bottleneck_op_min > 0:
        ceiling = 60.0 / inp.bottleneck_op_min
        if raw > ceiling:
            raw = ceiling
            capped_by_bottleneck = True

    suggested = max(1, int(raw))                               # round down — we don't promise fractional pieces
    daily = int(suggested * (inp.working_minutes / 60.0))
    takt = (60.0 / suggested) if suggested > 0 else 0.0

    notes.append(
        f"At {inp.operators} operators × {inp.efficiency_pct:.0f}% efficiency "
        f"and {inp.total_sam_min:.2f} min/garment, the line can produce "
        f"~{suggested}/hr ({daily}/day on a {inp.working_minutes}-minute shift)."
    )
    if capped_by_bottleneck:
        notes.append(
            f"Capped by the bottleneck op {inp.bottleneck_op_code or ''} "
            f"({inp.bottleneck_op_min:.3f} min). Beyond ~{int(60/inp.bottleneck_op_min)}/hr "
            f"you must split or speed up that operation, regardless of operator count."
        )
    if inp.efficiency_pct < 60:
        notes.append("Efficiency below 60% is typical of a new-style ramp-up.")
    elif inp.efficiency_pct > 90:
        notes.append("Efficiency above 90% is a stretch goal — only sustained on world-class lines.")

    # Reverse: at target, how many operators do we need?
    n_required = None
    if inp.target_output_hour:
        n_required = ceil(inp.target_output_hour * inp.total_sam_min / (eff_frac * 60.0))
        delta = n_required - inp.operators
        if delta > 0:
            notes.append(
                f"To hit {inp.target_output_hour}/hr at {inp.efficiency_pct:.0f}% "
                f"efficiency you would need ~{n_required} operators "
                f"({delta:+d} vs the current {inp.operators})."
            )
        elif delta < 0:
            notes.append(
                f"At {inp.target_output_hour}/hr you would only need ~{n_required} "
                f"operators — current staffing of {inp.operators} has spare capacity "
                f"({-delta} ops free for cross-training or absorbing absences)."
            )
        else:
            notes.append(
                f"Current staffing of {inp.operators} matches what's needed for "
                f"{inp.target_output_hour}/hr at {inp.efficiency_pct:.0f}%."
            )

    return SuggestionResult(
        suggested_output_hour=suggested,
        suggested_output_day=daily,
        takt_time_min=round(takt, 4),
        theoretical_operators_at_target=n_required,
        notes=notes,
    )
