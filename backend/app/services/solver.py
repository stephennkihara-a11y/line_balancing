"""
Line Balancing Solver — OR-Tools CP-SAT
=======================================

Input contract (`SolverInput`):
- operations: ordered list of operations with sam (min), machine_type, skill_level
- precedence: list of (predecessor_idx, successor_idx) on operation indices
- operators: list with id, base_efficiency, attendance_present, machine_compat (set
  of machine types they're certified to run, derived from skill matrix)
- skill_matrix: dict[(operator_idx, op_idx)] -> efficiency % (>0 means certified)
- machines_available: count by machine type
- target_output_hour, working_minutes

Output contract (`SolverResult`):
- assignments: list[(op_idx, station_idx, operator_idx, cycle_time_min)]
- station_load: list[float] cycle time per station in minutes
- takt_time, line_efficiency (%), balance_loss (%), bottleneck_station, status

Approach
--------
We model balancing as a generalised assembly-line balancing problem (GALBP-2):
- decide the number of stations N (= available operators, capped)
- assign each operation to exactly one station and one operator
- each operator works at exactly one station (one station per operator)
- precedence: station(pred) <= station(succ)
- skill: only operators with efficiency > 0 on op may take it
- machine: at most M[t] stations may use machine type t simultaneously
- objective: minimise the cycle time (max station load), i.e. minimise the
  bottleneck. This is equivalent to maximising line efficiency for fixed N.

A heuristic RPW seed is computed and supplied as an initial hint to CP-SAT
to accelerate convergence on large instances.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from ortools.sat.python import cp_model


# ---------- DTOs ----------------------------------------------------------
@dataclass
class OpDTO:
    idx: int                       # 0-based dense index
    op_id: int
    op_code: str
    sam: float                     # standard minutes
    machine_type: str
    skill_level: int


@dataclass
class OperatorDTO:
    idx: int                       # 0-based dense index
    operator_id: int
    name: str
    base_efficiency: float         # % (100 = on-target)


@dataclass
class SolverInput:
    operations: list[OpDTO]
    operators: list[OperatorDTO]
    precedence: list[tuple[int, int]]                 # (pred_idx, succ_idx)
    skill_matrix: dict[tuple[int, int], float]        # (op_idx, op_idx) -> efficiency %
    machines_available: dict[str, int] = field(default_factory=dict)
    target_output_hour: int = 60
    working_minutes: int = 480
    time_limit_s: int = 30


@dataclass
class AssignmentDTO:
    op_idx: int
    station: int                   # 1-based station number (= operator station)
    operator_idx: int
    cycle_time: float              # minutes for this op at this operator
    machine_type: str


@dataclass
class SolverResult:
    status: str                    # OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN
    assignments: list[AssignmentDTO]
    station_cycle_min: list[float]  # length N, in minutes
    takt_time: float                # minutes/piece
    theoretical_ops: int
    line_efficiency: float          # %
    balance_loss: float             # %
    bottleneck_station: int | None  # 1-based
    warnings: list[str] = field(default_factory=list)


# ---------- Helpers -------------------------------------------------------
SCALE = 1000  # convert minutes -> integer units (3 decimal places)


def _cycle_time_min(sam: float, op_efficiency_pct: float, base_efficiency_pct: float) -> float:
    """Effective cycle time = sam * 100 / (op_efficiency * base_efficiency / 100).

    Both efficiencies are percentages where 100 means on-standard.
    """
    eff = max(op_efficiency_pct, 0.1) * max(base_efficiency_pct, 0.1) / 100.0
    return sam * 100.0 / eff


def compute_takt(target_output_hour: int) -> float:
    if target_output_hour <= 0:
        return float("inf")
    return 60.0 / target_output_hour


def _ranked_positional_weight(ops: list[OpDTO], precedence: list[tuple[int, int]]) -> list[int]:
    """Return op indices sorted by descending positional weight (RPW).

    Positional weight = sam(op) + sum(sam of all descendants).
    """
    successors: dict[int, set[int]] = defaultdict(set)
    for p, s in precedence:
        successors[p].add(s)

    memo: dict[int, float] = {}

    def rpw(i: int) -> float:
        if i in memo:
            return memo[i]
        v = ops[i].sam
        for s in successors[i]:
            v += rpw(s)
        memo[i] = v
        return v

    return sorted(range(len(ops)), key=lambda i: rpw(i), reverse=True)


# ---------- Heuristic seed -----------------------------------------------
def _heuristic_seed(inp: SolverInput, n_stations: int, takt: float) -> dict[int, int] | None:
    """RPW + greedy operator pick. Returns {op_idx -> station} or None."""
    order = _ranked_positional_weight(inp.operations, inp.precedence)
    ready = set()
    successors: dict[int, set[int]] = defaultdict(set)
    predecessors: dict[int, set[int]] = defaultdict(set)
    for p, s in inp.precedence:
        successors[p].add(s)
        predecessors[s].add(p)

    placed: dict[int, int] = {}
    station_load = [0.0] * n_stations
    op_done = [False] * len(inp.operations)
    op_to_station = {}

    # operator station mapping is implicit (one operator per station, fixed by load)
    operator_station = list(range(n_stations))  # initial: operator i -> station i

    pending = order[:]
    while pending:
        progressed = False
        for op_idx in pending[:]:
            if any(not op_done[p] for p in predecessors[op_idx]):
                continue
            # find a station with an operator that can do op
            best = None
            for st in range(n_stations):
                op_idx_op = operator_station[st]
                if op_idx_op >= len(inp.operators):
                    continue
                eff = inp.skill_matrix.get((op_idx_op, op_idx), 0.0)
                if eff <= 0:
                    continue
                ct = _cycle_time_min(inp.operations[op_idx].sam, eff, inp.operators[op_idx_op].base_efficiency)
                new_load = station_load[st] + ct
                if new_load <= takt * 1.05:  # allow tiny slack
                    score = new_load
                    if best is None or score < best[0]:
                        best = (score, st, ct)
            if best is None:
                # fall back: any station whose operator can do it
                for st in range(n_stations):
                    op_idx_op = operator_station[st]
                    if op_idx_op >= len(inp.operators):
                        continue
                    eff = inp.skill_matrix.get((op_idx_op, op_idx), 0.0)
                    if eff <= 0:
                        continue
                    ct = _cycle_time_min(inp.operations[op_idx].sam, eff, inp.operators[op_idx_op].base_efficiency)
                    new_load = station_load[st] + ct
                    if best is None or new_load < best[0]:
                        best = (new_load, st, ct)
            if best is None:
                return None  # cannot place
            _, st, ct = best
            placed[op_idx] = st
            station_load[st] += ct
            op_done[op_idx] = True
            op_to_station[op_idx] = st
            pending.remove(op_idx)
            progressed = True
        if not progressed:
            return None
    return op_to_station


# ---------- Solver -------------------------------------------------------
def solve(inp: SolverInput) -> SolverResult:
    n_ops = len(inp.operations)
    n_ops_avail = len(inp.operators)
    warnings: list[str] = []

    if n_ops == 0:
        return SolverResult("INFEASIBLE", [], [], 0, 0, 0, 0, None, ["No operations supplied"])
    if n_ops_avail == 0:
        return SolverResult("INFEASIBLE", [], [], 0, 0, 0, 0, None, ["No operators available"])

    takt = compute_takt(inp.target_output_hour)
    total_sam = sum(o.sam for o in inp.operations)
    theoretical_ops = max(1, int((total_sam / takt) + 0.999)) if takt < float("inf") else n_ops_avail
    n_stations = min(n_ops_avail, max(theoretical_ops, 1))
    n_stations = min(n_stations, n_ops)  # never more stations than ops

    if n_stations < theoretical_ops:
        warnings.append(
            f"Only {n_stations} operators available but {theoretical_ops} "
            f"theoretically required for target {inp.target_output_hour}/hr. "
            f"Solver will minimise bottleneck instead."
        )

    # Pre-compute integer cycle times (scaled)
    # cycle[op][operator] = minutes scaled, or None if not certified
    cycle = [[None] * n_ops_avail for _ in range(n_ops)]
    for op in inp.operations:
        for opr in inp.operators:
            eff = inp.skill_matrix.get((opr.idx, op.idx), 0.0)
            if eff > 0:
                ct_min = _cycle_time_min(op.sam, eff, opr.base_efficiency)
                cycle[op.idx][opr.idx] = int(round(ct_min * SCALE))

    # Each op needs at least one operator
    for op in inp.operations:
        if all(c is None for c in cycle[op.idx]):
            warnings.append(f"Operation {op.op_code} has no certified operator; assigning by machine_type fallback")
            # Fallback: assume any operator can do it at 50% efficiency for solver continuity
            for opr in inp.operators:
                ct_min = _cycle_time_min(op.sam, 50.0, opr.base_efficiency)
                cycle[op.idx][opr.idx] = int(round(ct_min * SCALE))

    model = cp_model.CpModel()

    # Decision: x[op, station] = 1 if op assigned to station
    x = {}
    for op in range(n_ops):
        for st in range(n_stations):
            x[op, st] = model.NewBoolVar(f"x_op{op}_st{st}")

    # Each op exactly one station
    for op in range(n_ops):
        model.AddExactlyOne(x[op, st] for st in range(n_stations))

    # Decision: y[operator, station] = 1 if operator assigned to station
    y = {}
    for opr in range(n_ops_avail):
        for st in range(n_stations):
            y[opr, st] = model.NewBoolVar(f"y_op{opr}_st{st}")

    # Each station has exactly one operator (when n_stations <= n_ops_avail)
    for st in range(n_stations):
        model.AddExactlyOne(y[opr, st] for opr in range(n_ops_avail))
    # Each operator at most one station
    for opr in range(n_ops_avail):
        model.Add(sum(y[opr, st] for st in range(n_stations)) <= 1)

    # Precedence: station(pred) <= station(succ)
    # st(op) = sum_st st * x[op,st]
    station_var = {}
    for op in range(n_ops):
        s = model.NewIntVar(0, n_stations - 1, f"station_op{op}")
        model.Add(s == sum(st * x[op, st] for st in range(n_stations)))
        station_var[op] = s
    for p, s in inp.precedence:
        model.Add(station_var[p] <= station_var[s])

    # Skill compatibility: x[op,st] * y[opr,st] only if cycle[op][opr] is feasible
    # Linearise: for each op, st: sum_{opr feasible} y[opr,st] >= x[op,st]
    for op in range(n_ops):
        feasible = [opr for opr in range(n_ops_avail) if cycle[op][opr] is not None]
        for st in range(n_stations):
            if feasible:
                model.Add(sum(y[opr, st] for opr in feasible) >= x[op, st])
            else:
                model.Add(x[op, st] == 0)

    # Machine availability: count stations using each machine_type <= machines_available[type]
    if inp.machines_available:
        type_to_ops: dict[str, list[int]] = defaultdict(list)
        for op in inp.operations:
            type_to_ops[op.machine_type].append(op.idx)
        for mtype, op_idxs in type_to_ops.items():
            avail = inp.machines_available.get(mtype, n_stations)
            # Stations that have at least one op of this type
            station_uses = []
            for st in range(n_stations):
                u = model.NewBoolVar(f"uses_{mtype}_st{st}")
                model.AddMaxEquality(u, [x[op, st] for op in op_idxs])
                station_uses.append(u)
            model.Add(sum(station_uses) <= avail)

    # Compute station load (scaled minutes). For each station, sum over ops of
    # the cycle time IF that op is assigned to that station AND that operator
    # is also at that station. We need a product x[op,st] * y[opr,st] * cycle.
    # To linearise, introduce z[op,st,opr] = x AND y, only for feasible (op,opr).
    z = {}
    station_load = [model.NewIntVar(0, 10**9, f"load_st{st}") for st in range(n_stations)]
    for st in range(n_stations):
        terms = []
        for op in range(n_ops):
            for opr in range(n_ops_avail):
                if cycle[op][opr] is None:
                    continue
                v = model.NewBoolVar(f"z_op{op}_st{st}_opr{opr}")
                model.AddBoolAnd([x[op, st], y[opr, st]]).OnlyEnforceIf(v)
                model.AddBoolOr([x[op, st].Not(), y[opr, st].Not()]).OnlyEnforceIf(v.Not())
                z[op, st, opr] = v
                terms.append(cycle[op][opr] * v)
        if terms:
            model.Add(station_load[st] == sum(terms))
        else:
            model.Add(station_load[st] == 0)

    # Objective: minimise max station load (the cycle time)
    cycle_time_var = model.NewIntVar(0, 10**9, "cycle_time")
    model.AddMaxEquality(cycle_time_var, station_load)
    model.Minimize(cycle_time_var)

    # Provide RPW seed as a hint
    seed = _heuristic_seed(inp, n_stations, takt)
    if seed:
        for op_idx, st in seed.items():
            model.AddHint(x[op_idx, st], 1)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(inp.time_limit_s)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolverResult(
            status=status_name,
            assignments=[],
            station_cycle_min=[],
            takt_time=takt,
            theoretical_ops=theoretical_ops,
            line_efficiency=0.0,
            balance_loss=100.0,
            bottleneck_station=None,
            warnings=warnings + [f"Solver could not find a feasible plan ({status_name})"],
        )

    # Extract solution
    assignments: list[AssignmentDTO] = []
    op_station: dict[int, int] = {}
    operator_station: dict[int, int] = {}
    station_operator: dict[int, int] = {}

    for opr in range(n_ops_avail):
        for st in range(n_stations):
            if solver.Value(y[opr, st]) == 1:
                operator_station[opr] = st
                station_operator[st] = opr

    for op in range(n_ops):
        for st in range(n_stations):
            if solver.Value(x[op, st]) == 1:
                op_station[op] = st
                opr = station_operator.get(st)
                ct_min = (cycle[op][opr] / SCALE) if (opr is not None and cycle[op][opr] is not None) else inp.operations[op].sam
                assignments.append(
                    AssignmentDTO(
                        op_idx=op,
                        station=st + 1,
                        operator_idx=opr if opr is not None else -1,
                        cycle_time=ct_min,
                        machine_type=inp.operations[op].machine_type,
                    )
                )
                break

    station_load_min = [solver.Value(v) / SCALE for v in station_load]
    cycle_time = max(station_load_min) if station_load_min else 0.0
    if cycle_time <= 0:
        line_eff = 0.0
        balance_loss = 100.0
    else:
        line_eff = (total_sam / (cycle_time * n_stations)) * 100.0
        balance_loss = 100.0 - line_eff
    bottleneck_station = (
        max(range(n_stations), key=lambda s: station_load_min[s]) + 1 if station_load_min else None
    )

    return SolverResult(
        status=status_name,
        assignments=sorted(assignments, key=lambda a: (a.station, a.op_idx)),
        station_cycle_min=station_load_min,
        takt_time=takt,
        theoretical_ops=theoretical_ops,
        line_efficiency=round(line_eff, 2),
        balance_loss=round(balance_loss, 2),
        bottleneck_station=bottleneck_station,
        warnings=warnings,
    )
