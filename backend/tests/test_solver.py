"""Smoke test for the OR-Tools solver, runnable without a DB."""
from app.services.solver import OpDTO, OperatorDTO, SolverInput, solve


def test_solver_basic():
    ops = [
        OpDTO(0, 1, "OP1", 0.5, "SNLS", 1),
        OpDTO(1, 2, "OP2", 0.6, "SNLS", 1),
        OpDTO(2, 3, "OP3", 0.4, "OL", 1),
        OpDTO(3, 4, "OP4", 0.7, "OL", 1),
    ]
    operators = [
        OperatorDTO(0, 100, "A", 100.0),
        OperatorDTO(1, 101, "B", 100.0),
    ]
    skill = {(0, 0): 100.0, (0, 1): 100.0, (1, 2): 100.0, (1, 3): 100.0}
    inp = SolverInput(
        operations=ops,
        operators=operators,
        precedence=[(0, 1), (2, 3)],
        skill_matrix=skill,
        machines_available={"SNLS": 2, "OL": 2},
        target_output_hour=30,
        time_limit_s=10,
    )
    result = solve(inp)
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.assignments) == 4
    print("Status:", result.status)
    print("Line eff:", result.line_efficiency)
    print("Bottleneck:", result.bottleneck_station)


if __name__ == "__main__":
    test_solver_basic()
