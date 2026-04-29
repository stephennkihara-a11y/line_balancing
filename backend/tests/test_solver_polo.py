"""Larger smoke test: solve the polo shirt with synthetic operators."""
from app.seed.polo_shirt import POLO_SHIRT_OPERATIONS, POLO_SHIRT_PRECEDENCE
from app.services.solver import OpDTO, OperatorDTO, SolverInput, solve
import random


def _build_input(target=60, n_operators=20):
    code_to_idx = {o["op_code"]: i for i, o in enumerate(POLO_SHIRT_OPERATIONS)}
    ops = [
        OpDTO(i, i + 1, o["op_code"], o["sam"], o["machine_type"], o["skill_level"])
        for i, o in enumerate(POLO_SHIRT_OPERATIONS)
    ]
    operators = [OperatorDTO(i, 100 + i, f"OP{i}", float(random.randint(75, 110))) for i in range(n_operators)]
    skill = {}
    rng = random.Random(0)
    for op in ops:
        certified = 0
        for opr in operators:
            if rng.random() < 0.6:
                skill[(opr.idx, op.idx)] = float(rng.randint(60, 120))
                certified += 1
        # ensure at least 2 certified
        i = 0
        while certified < 2 and i < n_operators:
            if (i, op.idx) not in skill:
                skill[(i, op.idx)] = float(rng.randint(70, 100))
                certified += 1
            i += 1

    precedence = [
        (code_to_idx[p], code_to_idx[s]) for p, s in POLO_SHIRT_PRECEDENCE
        if p in code_to_idx and s in code_to_idx
    ]
    machines = {"SNLS": 12, "OL": 8, "FOA": 4, "BARTACK": 2, "BUTTON": 2, "BUTTONHOLE": 2, "IRON": 2, "MANUAL": 6}
    return SolverInput(
        operations=ops, operators=operators, precedence=precedence,
        skill_matrix=skill, machines_available=machines,
        target_output_hour=target, working_minutes=480, time_limit_s=15,
    )


def main():
    inp = _build_input(target=60, n_operators=20)
    result = solve(inp)
    print(f"Status: {result.status}")
    print(f"Stations: {len(result.station_cycle_min)}")
    print(f"Takt: {result.takt_time:.3f}  Theoretical ops: {result.theoretical_ops}")
    print(f"Line eff: {result.line_efficiency}%   Balance loss: {result.balance_loss}%")
    print(f"Bottleneck station: {result.bottleneck_station}")
    print(f"Warnings: {result.warnings}")
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.assignments) == len(POLO_SHIRT_OPERATIONS)


if __name__ == "__main__":
    main()
